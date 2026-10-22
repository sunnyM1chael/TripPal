import test from 'node:test'
import assert from 'node:assert/strict'
import { draftToBlogContent } from '../src/utils/visitFeedback.js'

test('体验草稿发布为转义后的文本，保留换行，不执行原始 HTML', () => {
  const output = draftToBlogContent(
    '<img src=x onerror="alert(1)">\r\n面 & 汤\n\'好吃\''
  )
  assert.equal(
    output,
    '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;<br>面 &amp; 汤<br>&#39;好吃&#39;'
  )
  assert.ok(!output.includes('<img'))
})
