import test from 'node:test'
import assert from 'node:assert/strict'
import { useFollowFeed } from '../src/composables/useFollowFeed.js'

test('关注动态传递服务端游标，保留长整数 ID，并在空页结束', async () => {
  const calls = []
  const pages = [
    {
      success: true,
      data: {
        list: [{ id: '9007199254740993', images: null }],
        minTime: 100,
        offset: 1
      }
    },
    {
      success: true,
      data: { list: [{ id: '9007199254740994' }], minTime: 90, offset: 1 }
    },
    { success: true }
  ]
  const feed = useFollowFeed(async (params) => {
    calls.push(params)
    return pages.shift()
  })
  await feed.load(true)
  assert.ok(calls[0].lastId > 0)
  assert.equal(calls[0].offset, 0)
  await feed.load()
  assert.deepEqual(calls[1], { lastId: 100, offset: 1 })
  assert.equal(feed.blogs.value.length, 2)
  await feed.load()
  await feed.load()
  assert.equal(feed.finished.value, true)
  assert.equal(calls.length, 3)
})

test('空收件箱正常展示；刷新清空旧动态', async () => {
  let response = {
    success: true,
    data: { list: [{ id: '1' }], minTime: 100, offset: 1 }
  }
  const feed = useFollowFeed(async () => response)
  await feed.load(true)
  response = { success: true }
  await feed.load(true)
  assert.deepEqual(feed.blogs.value, [])
  assert.equal(feed.error.value, '')
  assert.equal(feed.finished.value, true)
})

test('加载失败可重试，失败不推进游标，并阻止并发请求', async () => {
  const calls = []
  let complete
  const feed = useFollowFeed((params) => {
    calls.push(params)
    return new Promise((resolve) => {
      complete = resolve
    })
  })
  const pending = feed.load(true)
  await feed.load()
  assert.equal(calls.length, 1)
  complete({ success: false, errorMsg: '暂时无法获取动态' })
  await pending
  assert.equal(feed.error.value, '暂时无法获取动态')
  assert.equal(feed.loading.value, false)
  const retry = feed.load()
  assert.deepEqual(calls[1], calls[0])
  complete({ success: true })
  await retry
  assert.equal(feed.error.value, '')
})
