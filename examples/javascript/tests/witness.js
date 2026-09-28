const assert = require('node:assert/strict');
const {clamp} = require('../src/logic.js');
assert.equal(clamp(2), 2, 'WITNESS_TARGET: positive value must be preserved');
