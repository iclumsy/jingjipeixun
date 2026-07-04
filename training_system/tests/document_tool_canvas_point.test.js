const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const scriptPath = path.join(__dirname, '..', 'static', 'js', 'document_tools_admin.js');
const source = fs.readFileSync(scriptPath, 'utf8');

const cropCanvas = {
  width: 1000,
  height: 600,
  getBoundingClientRect() {
    return { left: 20, top: 30, width: 500, height: 300 };
  }
};
const elements = {
  cropCanvas,
  inputList: { innerHTML: '' },
  outputList: { innerHTML: '' },
  previewPanel: { hidden: true },
  resultActions: { hidden: false }
};

const context = {
  document: {
    getElementById(id) {
      return elements[id] || null;
    },
    addEventListener() {},
    querySelectorAll() {
      return [];
    }
  },
  window: {
    addEventListener() {}
  },
  assert
};

vm.createContext(context);
vm.runInContext(source, context);
vm.runInContext(`
  const scaledPoint = canvasPoint(document.getElementById('cropCanvas'), { clientX: 270, clientY: 180 });
  assert.deepStrictEqual(scaledPoint, [500, 300]);
  state.previewUrls.id_card_front = { name: 'front.jpg', url: 'blob:front' };
  renderSelectedPreviews();
  assert.strictEqual(document.getElementById('previewPanel').hidden, false);
  assert.strictEqual(document.getElementById('resultActions').hidden, true);
  assert(document.getElementById('inputList').innerHTML.includes('身份证正面'));
  assert(document.getElementById('inputList').innerHTML.includes('front.jpg'));
  assert(document.getElementById('outputList').innerHTML.includes('生成后显示结果'));
`, context);
