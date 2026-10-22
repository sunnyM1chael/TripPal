import test from 'node:test'
import assert from 'node:assert/strict'
import { usePlaceSearch } from '../src/composables/usePlaceSearch.js'

function deferred() {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}

test('selecting an origin fills origin and advances to destination', async () => {
  const selections = []
  const place = { poi_id: 'POI001', name: '常州站' }
  const state = usePlaceSearch({
    city: () => '常州',
    lookup: async () => ({ places: [place] }),
    onSelect: (...args) => selections.push(args)
  })
  assert.equal(state.field.value, 'origin')
  state.keyword.value = '常州站'
  await state.search()
  state.select(place)
  assert.deepEqual(selections, [['origin', place]])
  assert.equal(state.field.value, 'destination')
  assert.equal(state.keyword.value, '')
  assert.deepEqual(state.places.value, [])
})

test('switching fields discards a late origin lookup without ending the new lookup', async () => {
  const old = deferred(),
    current = deferred()
  let calls = 0
  const state = usePlaceSearch({
    city: () => '常州',
    lookup: () => (++calls === 1 ? old.promise : current.promise),
    onSelect() {}
  })
  state.keyword.value = '车站'
  const first = state.search()
  state.activate('destination')
  state.keyword.value = '公园'
  const second = state.search()
  old.resolve({ places: [{ poi_id: 'old' }] })
  await first
  assert.equal(state.searching.value, true)
  assert.deepEqual(state.places.value, [])
  current.resolve({ places: [{ poi_id: 'new' }] })
  await second
  assert.equal(state.searching.value, false)
  assert.equal(state.places.value[0].poi_id, 'new')
})

test('city changes and keyword edits invalidate search results', async () => {
  let city = '常州'
  const response = deferred()
  const state = usePlaceSearch({
    city: () => city,
    lookup: () => response.promise,
    onSelect() {
      assert.fail('stale selection')
    }
  })
  state.keyword.value = '车站'
  const pending = state.search()
  city = '苏州'
  state.activate('origin')
  response.resolve({ places: [{ poi_id: 'old' }] })
  await pending
  assert.deepEqual(state.places.value, [])
  state.select({ poi_id: 'old' })
  state.places.value = [{ poi_id: 'new' }]
  state.cancel()
  assert.deepEqual(state.places.value, [])
})
