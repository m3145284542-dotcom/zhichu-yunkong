const _fs = require('fs');
const _path = require('path');
const _src = [0,1,2,3]
  .map(i => _fs.readFileSync(_path.join(__dirname, `build_phase13_3_presentation.part${i}.jsfrag`), 'utf8'))
  .join('');
eval(_src);
