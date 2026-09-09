"""Package existing competition artifacts without changing scientific sources."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team-id', default='待填团队编号')
    parser.add_argument('--work-name', default='智储云控')
    args = parser.parse_args()
    for value in (args.team_id, args.work_name):
        if not value.strip() or re.search(r'[<>:"/\\|?*\x00-\x1f]', value) or value.endswith(('.', ' ')):
            parser.error('编号或作品名称包含文件名不支持的字符')
    prefix = f'{args.team_id}-AI+能源-{args.work_name}'
    dest = ROOT / 'outputs/competition_delivery' / prefix
    video = ROOT / 'outputs/demo_video/DOEF_Demo_Narrated.mp4'
    video_manifest_path = ROOT / 'outputs/demo_video/manifest.json'
    video_ready = video.exists() and video_manifest_path.exists()
    if video_ready:
        video_manifest = json.loads(video_manifest_path.read_text(encoding='utf-8'))
        if video_manifest['status'] != 'canonical' or video_manifest['sha256'] != sha(video.read_bytes()):
            raise RuntimeError('视频尚未验收或哈希不一致')
    outer = dest.with_name(dest.name + ('-材料整理包-含配音视频.zip' if video_ready else '-材料整理包-待补视频.zip'))
    if dest.exists() or outer.exists():
        parser.error('同名输出已存在；请保留原包并先改名，再重新生成')
    qa = json.loads((ROOT / 'reports/submission/qa/validation.json').read_text(encoding='utf-8'))
    if qa['status'] != 'PASS':
        raise RuntimeError('请先运行 reports/submission/validate_submission.py 并通过检查')
    report = ROOT / 'reports/submission/technical_report_submission.pdf'
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

    copy('reports/submission/technical_report_submission.pdf', upload, '技术报告')
    copy('outputs/submission/DOEF_Competition_Presentation.pdf', upload, '答辩PPT')
    copy('outputs/submission/DOEF_Competition_Presentation.pptx', cloud, '答辩PPT可编辑备份')
    copy('outputs/gui_demo/DOEF_Dynamic_Demo.html', cloud, '离线系统演示')
    if video_ready:
        copy('outputs/demo_video/DOEF_Demo_Narrated.mp4', upload, '演示视频')
        copy('outputs/demo_video/DOEF_Demo_Narrated.mp4', cloud, '演示视频')

    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    extras = ['docs/SUBMISSION_CHECKLIST.md', 'scripts/package_competition_submission.py']
    if video_ready:
        extras += ['scripts/build_demo_video.py', 'scripts/validate_demo_video.py',
                   'outputs/demo_video/README.md', 'outputs/demo_video/narration.md',
                   'outputs/demo_video/DOEF_Demo_Narrated.srt', 'outputs/demo_video/manifest.json',
                   'outputs/demo_video/validation.json']
    files = sorted(set(p for p in tracked + extras if p and not p.startswith('outputs/competition_delivery/')))
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
    records.append({'path': code_zip.relative_to(dest).as_posix(), 'source': 'git tracked working files + packaging additions',
                    'sha256': sha(code_zip.read_bytes()), 'bytes': code_zip.stat().st_size})

    deploy = '''智储云控部署与复核说明

一、无需安装的演示
双击同目录的“离线系统演示.html”，使用现代桌面浏览器打开。
所有样式、脚本和冻结数据均已内嵌。可切换建筑、日期及巡演模式。
这是已有离线实验回放，不是实时训练、在线调度或现场硬件控制，也不是MP4视频。

二、Python原型
解压“代码与实验材料.zip”，进入project目录。安装Python 3.11或以上版本。
运行：python gui/server.py
在浏览器打开 http://127.0.0.1:8765 。此演示仅需Python标准库。

三、现有成果复核
在project目录执行：
python -m pip install -r requirements.txt
python -m pip install PyMuPDF
python reports/submission/validate_submission.py
python -m unittest discover -s tests -p test_gui.py -v
材料验证不需要下载原始数据或重新训练。查看outputs/phase9/final_benchmark.csv、
outputs/phase9_1/final_reporting_summary.json和outputs/phase8/selected_weights.csv可核对核心结果。

四、数据获取与完整实验
原始BDG2大数据未随GitHub仓库提供；获取方式、官方文件路径和许可署名在docs/DATASET.md。
运行python scripts/download_bdg2.py，下载到data/raw/。下载失败按文档从官方源手工获取。
完整阶段依赖及执行顺序见docs/DEVELOPMENT_HISTORY.md；不要把早期教育园区聚合数据当作最终八栋办公建筑数据。
完整实验会写入outputs/phase*/，应在独立副本中执行。本次整理未重新训练或验证全链条重跑。
部分历史审计依赖Git历史；需要重跑这类审计时，应克隆原仓库并保留其历史，而不是只用无.git的ZIP。
仓库：https://github.com/m3145284542-dotcom/zhichu-yunkong

五、成果入口
报告：reports/submission/technical_report_submission.pdf
答辩PDF：outputs/submission/DOEF_Competition_Presentation.pdf
可编辑PPT：outputs/submission/DOEF_Competition_Presentation.pptx
讲稿：docs/REPORT_AND_DEFENSE_GUIDE.md
当前成果清单：reports/submission/manifest.json
其他phase目录为历史阶段及复现证据，不是应另行上传的报告版本。
'''
    (cloud / f'{prefix}-部署说明.txt').write_text(deploy, encoding='utf-8-sig')
    (dest / '提交清单.md').write_text((ROOT / 'docs/SUBMISSION_CHECKLIST.md').read_text(encoding='utf-8') +
        f'\n\n本包文件前缀：`{prefix}`。' + ('已包含配音 MP4，' if video_ready else '视频缺失，') + '网盘分享链接尚未创建。\n', encoding='utf-8-sig')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'schema_version': 1, 'status': 'candidate', 'role': 'local submission preparation, not submitted',
                'producer': 'scripts/package_competition_submission.py',
                'created_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': commit,
                'source_repository': 'https://github.com/m3145284542-dotcom/zhichu-yunkong',
                'team_id': args.team_id, 'work_name': args.work_name,
                'blocking_items': ([] if video_ready else ['MP4 video missing']) + ['Baidu permanent share not created'] +
                                  (['team id missing'] if args.team_id == '待填团队编号' else []),
                'checks': {'archive_integrity': True, 'copied_bytes_identical': True,
                           'source_material_validation': qa['status'], 'checks_passed': qa['checks_passed']},
                'local_changes': subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines(),
                'artifacts': records, 'source_inventory': inventory,
                'limitations': ['No full model rerun', 'No portal or Baidu upload', 'Team/work name must match registration']}
    for p in [dest / '提交清单.md', cloud / f'{prefix}-部署说明.txt']:
        manifest['artifacts'].append({'path': p.relative_to(dest).as_posix(), 'source': 'packaging documentation',
                                      'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size})
    (dest / '材料来源与校验.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with zipfile.ZipFile(outer, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():
                z.write(p, (Path(prefix) / p.relative_to(dest)).as_posix())
    with zipfile.ZipFile(outer) as z:
        assert z.testzip() is None
    print(json.dumps({'folder': str(dest), 'zip': str(outer), 'zip_bytes': outer.stat().st_size,
                      'source_files': len(files), 'status': manifest['status']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
