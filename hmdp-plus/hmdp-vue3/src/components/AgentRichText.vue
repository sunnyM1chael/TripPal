<script setup>
import { computed } from 'vue'

const props = defineProps({ text: { type: String, default: '' } })
// Render a small Markdown subset with Vue text nodes; never execute model HTML or links.
const inline = (text) =>
  text
    .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith('**') && part.endsWith('**'))
        return { tag: 'strong', text: part.slice(2, -2) }
      if (part.startsWith('`') && part.endsWith('`'))
        return { tag: 'code', text: part.slice(1, -1) }
      return { tag: 'span', text: part }
    })
const cells = (line) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
const blocks = computed(() => {
  const result = []
  const lines = props.text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line || /^---+$/.test(line)) continue
    if (
      line.includes('|') &&
      /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1] || '')
    ) {
      const rows = []
      const headers = cells(line)
      i += 2
      while (i < lines.length && lines[i].includes('|') && lines[i].trim())
        rows.push(cells(lines[i++]))
      i--
      result.push({ type: 'table', headers, rows })
    } else if (/^#{1,6}\s/.test(line)) {
      result.push({ type: 'heading', text: line.replace(/^#{1,6}\s+/, '') })
    } else if (/^([-*•]|\d+[.)、])\s+/.test(line)) {
      result.push({
        type: 'item',
        text: line.replace(/^([-*•]|\d+[.)、])\s+/, '')
      })
    } else {
      result.push({ type: 'paragraph', text: line })
    }
  }
  return result
})
</script>

<template>
  <div class="agent-rich-text">
    <template v-for="(block, i) in blocks" :key="i">
      <div v-if="block.type === 'table'" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th v-for="(cell, c) in block.headers" :key="c">
                <component
                  :is="part.tag"
                  v-for="(part, p) in inline(cell)"
                  :key="p"
                  >{{ part.text }}</component
                >
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, r) in block.rows" :key="r">
              <td v-for="(cell, c) in row" :key="c">
                <component
                  :is="part.tag"
                  v-for="(part, p) in inline(cell)"
                  :key="p"
                  >{{ part.text }}</component
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <component
        :is="block.type === 'heading' ? 'h3' : 'p'"
        v-else
        :class="{ 'list-item': block.type === 'item' }"
      >
        <component
          :is="part.tag"
          v-for="(part, p) in inline(block.text)"
          :key="p"
          >{{ part.text }}</component
        >
      </component>
    </template>
  </div>
</template>

<style scoped>
.agent-rich-text {
  line-height: 1.85;
  overflow-wrap: anywhere;
}
p {
  margin: 7px 0;
  white-space: pre-wrap;
}
h3 {
  font-size: 15px;
  margin: 17px 0 6px;
  color: var(--tp-ink);
}
.list-item {
  padding-left: 16px;
  position: relative;
}
.list-item::before {
  content: '•';
  position: absolute;
  left: 1px;
  color: var(--tp-muted);
}
code {
  background: #f2f1f7;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 0.9em;
}
.table-scroll {
  overflow-x: auto;
  margin: 12px 0;
}
table {
  border-collapse: collapse;
  min-width: 100%;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 9px 12px;
  border: 1px solid #eae8ee;
  min-width: 85px;
}
th {
  background: #f8f6fa;
  font-weight: 600;
}
</style>
