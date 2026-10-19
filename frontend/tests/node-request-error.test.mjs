import assert from 'node:assert/strict';
import {test} from 'node:test';
import {nodeRequestError} from '../src/utils/nodeRequestError.mjs';
const response = data => ({response:{data},message:'Request rejected'});
test('422 details use known field labels and retain multiple messages',()=>{
  assert.equal(nodeRequestError(response({detail:[{loc:['body','ssh_port'],msg:'Use a positive port'},{loc:['body','controller_url'],msg:'HTTPS required'}]}),{ssh_port:'پورت SSH',controller_url:'کنترلر'}),'پورت SSH: Use a positive port · کنترلر: HTTPS required');
});
test('plain server errors retain their message',()=>{
  assert.equal(nodeRequestError(response({detail:'Verify the SSH host fingerprint'})),'Verify the SSH host fingerprint');
});
test('object messages never serialize input or context',()=>{
  assert.equal(nodeRequestError(response({detail:{message:'Invalid node request',input:'secret',ctx:{secret:'secret'}}})),'Invalid node request');
});
test('unknown objects and non-string messages use safe fallbacks',()=>{
  assert.equal(nodeRequestError(response({detail:[{msg:{secret:'secret'},input:'secret'}],msg:'Safe fallback'})),'Safe fallback');
  assert.equal(nodeRequestError(response({detail:{input:'secret'}})),'Request rejected');
  assert.equal(nodeRequestError({response:{data:{detail:{ctx:'secret'}}}}),'Operation failed');
});
test('unknown location components and prototype names are never rendered',()=>{
  assert.equal(nodeRequestError(response({detail:[{loc:['body','private-input','__proto__','constructor'],msg:'Invalid field'}]}),{ssh_port:'SSH Port'}),'Invalid field');
});
test('validation metadata is not stringified or coerced',()=>{
  const forbidden={toString(){throw new Error('Do not coerce validation input');}};
  assert.equal(nodeRequestError(response({detail:[{loc:['body',forbidden],msg:'Invalid field',input:forbidden,ctx:forbidden}]})),'Invalid field');
});
