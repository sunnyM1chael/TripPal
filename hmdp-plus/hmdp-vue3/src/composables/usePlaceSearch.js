import { ref } from 'vue'

// Each result list belongs to one field and one city; late responses are discarded.
export function usePlaceSearch({ city, lookup, onSelect, onMissingCity }) {
  const field = ref('origin')
  const keyword = ref('')
  const places = ref([])
  const searching = ref(false)
  const searchError = ref('')
  const searched = ref(false)
  let version = 0

  function cancel() {
    version++
    searching.value = false
    places.value = []
    searchError.value = ''
    searched.value = false
  }
  function activate(value) {
    cancel()
    field.value = value
    keyword.value = ''
  }
  async function search() {
    const query = keyword.value.trim()
    if (!query || searching.value) return
    if (!city()) {
      onMissingCity()
      return
    }
    cancel()
    const turn = version
    const target = field.value
    const selectedCity = city()
    searching.value = true
    try {
      const data = await lookup(selectedCity, query)
      if (turn !== version || target !== field.value || selectedCity !== city())
        return
      places.value = data.places
      searched.value = true
    } catch (error) {
      if (turn === version) searchError.value = error.message
    } finally {
      if (turn === version) searching.value = false
    }
  }
  function select(place) {
    if (!places.value.includes(place)) return
    onSelect(field.value, place)
    activate('destination')
  }
  return {
    field,
    keyword,
    places,
    searching,
    searchError,
    searched,
    cancel,
    activate,
    search,
    select
  }
}
