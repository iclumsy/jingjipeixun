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

  state.previewUrls.id_card_front = { name: '"><img src=x onerror=alert(1)>', url: 'blob:evil' };
  renderSelectedPreviews();
  assert(!document.getElementById('inputList').innerHTML.includes('<img src=x onerror=alert(1)>'));
  assert(document.getElementById('inputList').innerHTML.includes('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;'));

  state.task = { id: 'task-a' };
  const guard = createTaskRequestGuard(() => state.task && state.task.id);
  const firstRequest = guard.next('task-a');
  const secondRequest = guard.next('task-a');
  assert.strictEqual(guard.isCurrent(firstRequest, 'task-a'), false);
  assert.strictEqual(guard.isCurrent(secondRequest, 'task-b'), false);
  state.task = { id: 'task-b' };
  assert.strictEqual(guard.isCurrent(secondRequest, 'task-a'), false);
  state.task = { id: 'task-a' };
  assert.strictEqual(guard.isCurrent(secondRequest, 'task-a'), true);
  guard.close();
  assert.strictEqual(guard.isCurrent(secondRequest, 'task-a'), false);
`, context);

assert(!source.includes('state.points[field.pointKey] = pts'), 'auto-detected points must not be stored as confirmed global points');
