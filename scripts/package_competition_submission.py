"""Package existing competition artifacts without changing scientific sources."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def current_materials():
    """Resolve the accepted report/deck pair, never fall back to an old release."""
    registry = json.loads((ROOT / 'reports/current_submission.json').read_text(encoding='utf-8'))
    release = json.loads((ROOT / registry['manifest']).read_text(encoding='utf-8'))
    if registry['status'] != 'canonical' or release['status'] != 'canonical':
        raise RuntimeError('当前省赛材料尚未验收')
    records = {item['path']: item for item in release['artifacts']}
    for key in ['report', 'deck_pdf', 'deck_pptx'] + (['video'] if 'video' in registry else []):
        path = registry[key]
        if path not in release['canonical_for_scope'] or sha((ROOT / path).read_bytes()) != records[path]['sha256']:
            raise RuntimeError('材料来源或散列不一致：' + path)
    if 'video_manifest' in registry:
        video_manifest=json.loads((ROOT/registry['video_manifest']).read_text(encoding='utf-8'))
        if video_manifest['status']!='canonical' or video_manifest['sha256']!=sha((ROOT/registry['video']).read_bytes()):
            raise RuntimeError('视频尚未验收或哈希不一致')
    return registry, release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team-id', default='AIC-2026-27833449')
    parser.add_argument('--work-name', default='智储云控')
    parser.add_argument('--revision', default='', help='Optional package revision; keeps previous packages intact')
    parser.add_argument('--check-materials', action='store_true', help='Validate current sources without creating an archive')
    args = parser.parse_args()
    material, release = current_materials()
    subprocess.run([sys.executable, str(ROOT / 'scripts/validate_final_delivery.py')], cwd=ROOT, check=True)
    qa = json.loads((ROOT / material['qa']).read_text(encoding='utf-8'))
    if qa['status'] != 'PASS':
        raise RuntimeError('省赛报告与 PPT 对齐检查失败')
    if args.check_materials:
        print(json.dumps(material, ensure_ascii=False, indent=2))
        return
    for value in (args.team_id, args.work_name):
        if not value.strip() or re.search(r'[<>:"/\\|?*\x00-\x1f]', value) or value.endswith(('.', ' ')):
            parser.error('编号或作品名称包含文件名不支持的字符')
    prefix = f'{args.team_id}-AI+能源-{args.work_name}'
    if args.revision and not re.fullmatch(r'[A-Za-z0-9_-]+', args.revision):
        parser.error('版本标签仅支持字母、数字、下划线和连字符')
    dest = ROOT / 'outputs/competition_delivery' / (prefix + ('-' + args.revision if args.revision else ''))
    video = ROOT / 'outputs/demo_video/DOEF_Demo_Narrated.mp4'
    video_manifest_path = ROOT / 'outputs/demo_video/manifest.json'
    video_ready = video.exists() and video_manifest_path.exists()
    if video_ready:
        video_manifest = json.loads(video_manifest_path.read_text(encoding='utf-8'))
        if video_manifest['status'] != 'canonical' or video_manifest['sha256'] != sha(video.read_bytes()):
            raise RuntimeError('视频尚未验收或哈希不一致')
        video_qa = json.loads((ROOT/'outputs/demo_video/validation.json').read_text(encoding='utf-8'))
        if (video_qa['status'] != 'PASS' or video_qa.get('sha256') != sha(video.read_bytes())
                or not 180 <= video_qa['duration_seconds'] <= 300 or video.stat().st_size > 300_000_000):
            raise RuntimeError('视频验收记录或提交规格不符合要求')
    outer = dest.with_name(dest.name + ('-材料整理包-含配音视频.zip' if video_ready else '-材料整理包-待补视频.zip'))
    if dest.exists() or outer.exists():
        parser.error('同名输出已存在；请保留原包并先改名，再重新生成')
    report = ROOT / material['report']
    if report.stat().st_size > 10_000_000:
        raise RuntimeError('报告超过 10 MB')
    upload = dest / '报名系统上传'
    cloud = dest / '百度网盘材料' / prefix
    upload.mkdir(parents=True)
    cloud.mkdir(parents=True)
    records = []

    def copy(source, folder, label):
        path = ROOT / source
        target = folder / f'{prefix}-{label}{path.suffix}'
        shutil.copy2(path, target)
        assert target.read_bytes() == path.read_bytes()
        records.append({'path': target.relative_to(dest).as_posix(), 'source': source,
                        'sha256': sha(target.read_bytes()), 'bytes': target.stat().st_size})

    copy(material['report'], upload, '技术报告')
    copy(material['deck_pdf'], upload, '答辩PPT')
    copy(material['deck_pptx'], cloud, '答辩PPT可编辑备份')
    copy('outputs/gui_demo/DOEF_Dynamic_Demo.html', cloud, '离线系统演示')
    copy(material['report'], cloud, '技术报告')
    copy(material['deck_pdf'], cloud, '答辩PPT')
    # The latest supplied version includes the advisor signatures; preserve all bytes.
    pledge = ROOT / 'output/pdf/pledge-signed.pdf'
    if pledge.exists():
        registration = dest / '报名附件（含个人信息，仅供报名）'
        registration.mkdir()
        copy(pledge.relative_to(ROOT).as_posix(), registration, '参赛承诺书')
    else:
        print('Private signed registration attachment is absent; public materials will still be packaged.')
    if video_ready:
        copy('outputs/demo_video/DOEF_Demo_Narrated.mp4', upload, '演示视频')
        copy('outputs/demo_video/DOEF_Demo_Narrated.mp4', cloud, '演示视频')
    preparation = dest / '本地备稿（无需上传）'
    preparation.mkdir()
    copy('reports/provincial_20261012/speaker_notes.md', preparation, '逐页答辩讲稿')
    copy('outputs/demo_video/narration.md', preparation, '视频讲解稿')
    copy('outputs/demo_video/DOEF_Demo_Narrated.srt', preparation, '视频字幕')

    # Current public tree only; deleted drafts and private/local bundles are excluded.
    listed = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    extras = [item['path'] for item in release['artifacts']]
    allowed = ('src/', 'scripts/', 'tests/', 'gui/', 'data/', 'docs/', 'reports/', 'outputs/', '.github/')
    top = {'.gitignore', '.gitattributes', 'README.md', 'requirements.txt', 'requirements-delivery.txt'}
    files = sorted({p for p in listed + extras if p and (ROOT/p).is_file()
                    and (p in top or p.startswith(allowed))
                    and not p.startswith(('outputs/competition_delivery/', 'data/raw/'))
                    and p != 'reports/current_delivery.json'
                    and '__pycache__' not in Path(p).parts})
    if any(Path(p).name.startswith('.env') or 'pledge' in p.lower() or 'signature-' in p.lower() for p in files):
        raise RuntimeError('源码清单包含私密配置或报名签名材料')
    inventory = []
    code_zip = cloud / f'{prefix}-代码与实验材料.zip'
    with zipfile.ZipFile(code_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for relative in files:
            data = (ROOT / relative).read_bytes()
            z.writestr('project/' + relative, data)
            inventory.append({'path': relative, 'sha256': sha(data), 'bytes': len(data)})
    with zipfile.ZipFile(code_zip) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(files)
        for item in inventory:
            assert sha(z.read('project/' + item['path'])) == item['sha256']
        # Exercise the delivered snapshot without using files from the working checkout.
        with tempfile.TemporaryDirectory(prefix='aic-package-') as temporary:
            extracted=Path(temporary)
            z.extractall(extracted)
            project=extracted/'project'
            subprocess.run([sys.executable, '-X', 'utf8', 'scripts/validate_final_delivery.py'], cwd=project, check=True)
            subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_gui.py', '-v'], cwd=project, check=True)
            bundled_video=json.loads((project/'outputs/demo_video/manifest.json').read_text(encoding='utf-8'))
            assert sha((project/bundled_video['artifact']).read_bytes())==bundled_video['sha256']
            for item in bundled_video['sources']+[bundled_video['gui_source']]:
                assert sha((project/item['path']).read_bytes())==item['sha256'], item['path']
    records.append({'path': code_zip.relative_to(dest).as_posix(), 'source': 'current public files + canonical release inventory',
                    'sha256': sha(code_zip.read_bytes()), 'bytes': code_zip.stat().st_size})

    deploy = f'''智储云控部署与复核说明

一、无需安装的演示
双击同目录以“离线系统演示.html”结尾的文件，使用现代桌面浏览器打开。
所有样式、脚本和冻结数据均已内嵌。可开始八建筑巡演，暂停、继续或切换至下一栋；结束后查看综合结果。
这是已有离线实验回放，不是实时训练、在线调度或现场硬件控制，也不是MP4视频。

二、Python原型
解压“代码与实验材料.zip”，进入project目录。安装Python 3.11或以上版本。
运行：python gui/server.py
在浏览器打开 http://127.0.0.1:8765 。此演示仅需Python标准库。

三、现有成果复核
在project目录执行：
python -m pip install -r requirements.txt
python -m pip install -r requirements-delivery.txt
python scripts/validate_final_delivery.py
python -m unittest discover -s tests -p test_gui.py -v
材料验证不需要下载原始数据或重新训练。查看outputs/phase9/final_benchmark.csv、
outputs/phase9_1/final_reporting_summary.json和outputs/phase8/selected_weights.csv可核对核心结果。

四、数据获取与完整实验
原始BDG2大数据未随GitHub仓库提供；获取方式、官方文件路径和许可署名在docs/DATASET.md。
运行python scripts/download_bdg2.py，下载到data/raw/。下载失败按文档从官方源手工获取。
完整阶段依赖及执行顺序见docs/REPRODUCING.md；不要把早期教育园区聚合数据当作最终八栋办公建筑数据。
完整实验会写入outputs/phase*/，应在独立副本中执行。本次整理未重新训练或验证全链条重跑。
部分历史审计依赖Git历史；需要重跑这类审计时，应克隆原仓库并保留其历史，而不是只用无.git的ZIP。
仓库：https://github.com/m3145284542-dotcom/zhichu-yunkong

五、成果入口
报告：{material['report']}
答辩PDF：{material['deck_pdf']}
可编辑PPT：{material['deck_pptx']}
讲稿：docs/REPORT_AND_DEFENSE_GUIDE.md
当前成果清单：{material['manifest']}
视频：outputs/demo_video/DOEF_Demo_Narrated.mp4
逐页答辩讲稿：reports/provincial_20261012/speaker_notes.md
phase3至phase9_1为冻结科研依据及复现依赖；旧报告和旧PPT已移出当前交付。
'''
    (cloud / f'{prefix}-部署说明.txt').write_text(deploy, encoding='utf-8-sig')
    checklist=f'''# 智储云控参赛提交清单

团队编号：{args.team_id}。作品名称：{args.work_name}。赛题：AI+能源，科技创新组。
本包为 {args.revision} 本地整理版本，尚未上传或提交。文件前缀已统一。

| 用途 | 目录与文件 | 已核验规格 |
| --- | --- | --- |
| 报名系统：技术报告 | 报名系统上传/{prefix}-技术报告.pdf | {qa['report_pages']}页，{report.stat().st_size/1e6:.2f} MB，低于10 MB |
| 报名系统：答辩PPT | 报名系统上传/{prefix}-答辩PPT.pdf | {qa['deck_pages']}页，提交PDF |
| 报名系统：演示视频 | 报名系统上传/{prefix}-演示视频.mp4 | {video_qa['duration_seconds']:.2f}秒，1080p，{video.stat().st_size/1e6:.2f} MB |
| 作品其他材料链接 | 百度网盘材料/{prefix}/ | 报告、答辩PDF/PPTX、视频、离线HTML、源码实验ZIP、部署说明 |
| 参赛承诺书 | 报名附件（含个人信息，仅供报名）/ | {'最新已签版本原样复制，仅用于报名系统对应栏目' if pledge.exists() else '当前机器缺少私密附件，报名时需另行补充'} |
| 本地讲稿及字幕 | 本地备稿（无需上传）/ | 逐页讲稿、视频讲稿、SRT |

## 提交顺序

1. 仅将“百度网盘材料”目录上传网盘，设置永久分享与提取码。不要分享含个人信息附件的完整整理包。
2. 在报名系统分别上传“报名系统上传”中的三份文件。
3. 在作品其他材料栏目填写真实网盘链接与提取码；按系统要求单独提交参赛承诺书。
4. 核对团队编号、作品名称及最终提交状态。省赛截止时间以省赛通知和报名系统为准。

代码与实验材料包保留复现所需相对目录；原始BDG2数据通过 docs/DATASET.md 与下载脚本提供获取方式。
已核对复制文件哈希、内外ZIP完整性，并在独立解包目录验证报告/PPT与GUI结果。未重新训练或运行调度实验。
视频使用 Microsoft Huihui 本机中文合成配音，包含新版12页PPT与真实离线GUI录像。
'''
    (dest/'提交清单.md').write_text(checklist,encoding='utf-8-sig')
    (dest/'00-先看这里.txt').write_text('本文件夹是当前新版参赛材料。\n\n1. 报名系统上传：报告PDF、答辩PDF、视频MP4。\n2. 百度网盘材料：只分享此目录，填写永久链接和提取码。\n3. 报名附件：含个人信息的已签承诺书，单独用于报名。\n4. 本地备稿：讲稿和字幕，无需上传。\n\n详细路径和规格见“提交清单.md”。完整整理ZIP用于本人保存和传输，不作为网盘公开分享包。尚未实际上传或提交。\n',encoding='utf-8-sig')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'schema_version': 1, 'status': 'canonical', 'submission_status': 'not_submitted', 'role': 'validated local submission package',
                'producer': 'scripts/package_competition_submission.py',
                'created_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': commit,
                'source_repository': 'https://github.com/m3145284542-dotcom/zhichu-yunkong',
                'team_id': args.team_id, 'work_name': args.work_name,
                'source_manifest_sha256': sha((ROOT / material['manifest']).read_bytes()),
                'acceptance_reason': 'Validated source materials; copied bytes and nested ZIP integrity checked',
                'blocking_items': ([] if video_ready else ['MP4 video missing']) + ['Baidu permanent share not created'] + ([] if pledge.exists() else ['Signed pledge not included']) +
                                  (['team id missing'] if args.team_id == '待填团队编号' else []),
                'checks': {'archive_integrity': True, 'copied_bytes_identical': True,
                           'source_material_validation': qa['status'], 'checks_passed': qa['checks_passed'],
                           'extracted_snapshot_alignment': True, 'extracted_gui_tests': 5,
                           'video_sources_complete': True, 'private_registration_isolated': True, 'signed_pledge_included': pledge.exists()},
                'local_changes': subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines(),
                'artifacts': records, 'source_inventory': inventory,
                'limitations': ['No full model rerun', 'No portal or Baidu upload', 'Team/work name must match registration']}
    for p in [dest / '提交清单.md', dest/'00-先看这里.txt', cloud / f'{prefix}-部署说明.txt']:
        manifest['artifacts'].append({'path': p.relative_to(dest).as_posix(), 'source': 'packaging documentation',
                                      'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size})
    (dest / '材料来源与校验.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with zipfile.ZipFile(outer, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():
                z.write(p, (Path(prefix) / p.relative_to(dest)).as_posix())
    with zipfile.ZipFile(outer) as z:
        assert z.testzip() is None
        for item in records:
            assert sha(z.read((Path(prefix)/item['path']).as_posix())) == item['sha256']
    pointer={'schema_version':1,'status':'canonical','submission_status':'not_submitted',
             'folder':dest.relative_to(ROOT).as_posix(),'zip':outer.relative_to(ROOT).as_posix(),
             'zip_sha256':sha(outer.read_bytes()),'zip_bytes':outer.stat().st_size,
             'manifest':(dest/'材料来源与校验.json').relative_to(ROOT).as_posix(),
             'source_manifest_sha256':manifest['source_manifest_sha256'],
             'created_utc':manifest['created_utc'],'producer':'scripts/package_competition_submission.py'}
    (ROOT/'reports/current_delivery.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'folder': str(dest), 'zip': str(outer), 'zip_bytes': outer.stat().st_size,
                      'source_files': len(files), 'status': manifest['status']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
