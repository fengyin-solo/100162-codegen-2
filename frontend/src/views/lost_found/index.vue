<template>
  <section class="page" data-module="lost-found">
    <header class="page-head">
      <div>
        <h2>遗失物品管理</h2>
        <p class="page-desc">受理捡拾记录并维护失物招领信息，支持旅客认领核销、批量移交与批量报废。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">受理捡拾记录</button>
        <button class="btn" type="button" @click="exportRows">导出现有清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="toolbar">
      <div class="tabs" role="tablist" aria-label="遗失物品状态">
        <button
          v-for="tab in statusTabs"
          :key="tab.value || 'all'"
          class="tab"
          :class="{ active: activeStatus === tab.value }"
          type="button"
          @click="changeStatus(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <form class="inline-filter" @submit.prevent="reload">
        <input v-model="keyword" placeholder="按编号、名称、类别或地点检索" />
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置</button>
      </form>
    </div>

    <div class="batch-bar">
      <label class="select-all">
        <input
          type="checkbox"
          :checked="allPendingSelected"
          :disabled="!pendingRows.length"
          @change="toggleSelectAll"
        />
        全选当前待认领
      </label>
      <span>已选 {{ selectedIds.length }} 条</span>
      <button class="btn" type="button" :disabled="!selectedIds.length" @click="openBatch('transfer')">
        批量移交
      </button>
      <button class="btn danger" type="button" :disabled="!selectedIds.length" @click="openBatch('scrap')">
        批量报废
      </button>
      <span v-if="batchHint" class="error-text">{{ batchHint }}</span>
    </div>

    <table class="data-table lost-table">
      <thead>
        <tr>
          <th class="check-col">选择</th>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>记录处理</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td class="check-col">
            <input
              v-if="row.status === STATUS_PENDING"
              type="checkbox"
              :checked="selectedIds.includes(Number(row.id))"
              @change="toggleRow(Number(row.id))"
            />
            <span v-else class="muted-text">—</span>
          </td>
          <td v-for="column in columns" :key="column">
            <span :class="{ 'status-pending': column === '状态' && row[column] === STATUS_PENDING }">
              {{ row[column] || '—' }}
            </span>
          </td>
          <td class="row-actions lost-actions">
            <button class="link" type="button" @click="openDetail(row)">查看</button>
            <button
              v-if="row.status === STATUS_PENDING"
              class="link"
              type="button"
              @click="openEdit(row)"
            >
              维护
            </button>
            <button
              v-if="row.status === STATUS_PENDING"
              class="link"
              type="button"
              @click="openClaim(row)"
            >
              认领核销
            </button>
            <button
              v-if="row.status === STATUS_PENDING"
              class="link"
              type="button"
              @click="openSingleBatch(row, 'transfer')"
            >
              移交
            </button>
            <button
              v-if="row.status === STATUS_PENDING"
              class="link danger-link"
              type="button"
              @click="openSingleBatch(row, 'scrap')"
            >
              报废
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无符合条件的遗失物品记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="formModal.show" class="modal-mask" @click.self="closeForm">
      <section class="modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>{{ formModal.mode === 'create' ? '受理捡拾记录' : '维护失物招领信息' }}</h3>
          <button class="modal-close" type="button" @click="closeForm">×</button>
        </header>
        <form @submit.prevent="submitForm">
          <div class="form-grid">
            <label v-for="field in formFields" :key="field.name" :class="{ required: field.required }">
              <span>{{ field.label }}</span>
              <input
                v-if="field.name !== '备注'"
                v-model="formModal.values[field.name]"
                :type="field.name === '捡拾日期' ? 'date' : 'text'"
                :placeholder="`请输入${field.label}`"
              />
              <textarea v-else v-model="formModal.values[field.name]" rows="3" />
            </label>
          </div>
          <p v-if="formModal.error" class="error-text">{{ formModal.error }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="closeForm">取消</button>
            <button class="btn primary" type="submit">{{ formModal.mode === 'create' ? '受理' : '保存' }}</button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="claimModal.show" class="modal-mask" @click.self="closeClaim">
      <section class="modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>旅客认领核销：{{ claimModal.row?.物品编号 }}</h3>
          <button class="modal-close" type="button" @click="closeClaim">×</button>
        </header>
        <form @submit.prevent="submitClaim">
          <div class="single-form">
            <label class="required">
              <span>认领人</span>
              <input v-model="claimModal.values.认领人" placeholder="请输入认领人姓名" />
            </label>
            <label class="required">
              <span>证件号</span>
              <input v-model="claimModal.values.证件号" placeholder="请输入证件号码" />
            </label>
            <label>
              <span>认领备注</span>
              <textarea v-model="claimModal.values.备注" rows="3" />
            </label>
          </div>
          <p v-if="claimModal.error" class="error-text">{{ claimModal.error }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="closeClaim">取消</button>
            <button class="btn primary" type="submit">登记并核销</button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="batchModal.show" class="modal-mask" @click.self="closeBatch">
      <section class="modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>{{ batchModal.action === 'transfer' ? '批量移交' : '批量报废' }}（{{ batchModal.ids.length }} 条）</h3>
          <button class="modal-close" type="button" @click="closeBatch">×</button>
        </header>
        <form @submit.prevent="submitBatch">
          <div class="single-form">
            <template v-if="batchModal.action === 'transfer'">
              <label class="required">
                <span>接收人</span>
                <input v-model="batchModal.values.接收人" placeholder="例如：公安执勤室-钱警官" />
              </label>
              <label class="required">
                <span>移交地点</span>
                <input v-model="batchModal.values.移交地点" placeholder="例如：T2 二层公安执勤室" />
              </label>
            </template>
            <label v-else class="required">
              <span>报废原因</span>
              <textarea v-model="batchModal.values.报废原因" rows="3" placeholder="请输入报废原因" />
            </label>
            <label>
              <span>备注</span>
              <textarea v-model="batchModal.values.备注" rows="3" />
            </label>
          </div>
          <p class="modal-tip">系统会逐条校验：其中一条不通过时只跳过该条，其余记录继续处理。</p>
          <p v-if="batchModal.error" class="error-text">{{ batchModal.error }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="closeBatch">取消</button>
            <button class="btn primary" type="submit">确认{{ batchModal.action === 'transfer' ? '移交' : '报废' }}</button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="detailEntry" class="modal-mask" @click.self="detailEntry = null">
      <section class="modal detail-modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>遗失物品明细</h3>
          <button class="modal-close" type="button" @click="detailEntry = null">×</button>
        </header>
        <dl class="detail-list">
          <div v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detailEntry[field] || '—' }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <div v-if="batchResults.length" class="modal-mask" @click.self="batchResults = []">
      <section class="modal result-modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>逐条处理结果</h3>
          <button class="modal-close" type="button" @click="batchResults = []">×</button>
        </header>
        <p>
          成功 {{ batchSuccessCount }} 条，跳过/失败 {{ batchFailureCount }} 条。
          未通过的记录保持原状态，仍可在待认领清单中处理。
        </p>
        <ul class="result-list">
          <li v-for="item in batchResults" :key="item.id" :class="item.ok ? 'result-ok' : 'result-fail'">
            <strong>{{ item.ok ? '成功' : '跳过' }}</strong>
            <span>#{{ item.id }}：{{ item.message }}</span>
          </li>
        </ul>
        <footer class="modal-foot">
          <button class="btn primary" type="button" @click="batchResults = []">知道了</button>
        </footer>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string> & { id: number }
type BatchItem = {
  id: number
  ok: boolean
  message: string
  entry: Row | null
}
type BatchResponse = {
  ok: boolean
  action: string
  results: BatchItem[]
  success_count: number
  failure_count: number
}
type ActionResponse = {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/lost-found'
const STATUS_PENDING = '待认领'
const STATUS_CLAIMED = '已认领'
const STATUS_TRANSFERRED = '已移交'
const STATUS_SCRAPPED = '已报废'

const columns = ['物品编号', '物品名称', '物品类别', '捡拾地点', '捡拾日期', '保管人', '状态']
const detailFields = [
  '物品编号', '物品名称', '物品类别', '物品特征', '捡拾地点', '捡拾日期', '捡拾人', '保管人',
  '认领人', '证件号', '接收人', '移交地点', '报废原因', '备注', 'status',
]
const statusTabs = [
  { label: '待认领清单', value: STATUS_PENDING },
  { label: '全部', value: '' },
  { label: '已认领', value: STATUS_CLAIMED },
  { label: '已移交', value: STATUS_TRANSFERRED },
  { label: '已报废', value: STATUS_SCRAPPED },
]
const formFields = [
  { name: '物品类别', label: '物品类别', required: true },
  { name: '物品名称', label: '物品名称', required: false },
  { name: '物品特征', label: '物品特征', required: false },
  { name: '捡拾地点', label: '捡拾地点', required: true },
  { name: '捡拾日期', label: '捡拾日期', required: false },
  { name: '捡拾人', label: '捡拾人', required: false },
  { name: '保管人', label: '保管人', required: true },
  { name: '备注', label: '备注', required: false },
] as const

const rows = ref<Row[]>([])
const total = ref(0)
const counts = ref<Record<string, number>>({})
const errorMessage = ref('')
const batchHint = ref('')
const keyword = ref('')
const activeStatus = ref(STATUS_PENDING)
const selectedIds = ref<number[]>([])
const detailEntry = ref<Row | null>(null)
const batchResults = ref<BatchItem[]>([])

const formModal = reactive({
  show: false,
  mode: 'create' as 'create' | 'edit',
  id: 0,
  error: '',
  values: emptyFormValues(),
})
const claimModal = reactive({
  show: false,
  row: null as Row | null,
  error: '',
  values: { 认领人: '', 证件号: '', 备注: '' },
})
const batchModal = reactive({
  show: false,
  action: 'transfer' as 'transfer' | 'scrap',
  ids: [] as number[],
  error: '',
  values: { 接收人: '', 移交地点: '', 报废原因: '', 备注: '' },
})

const stats = computed(() => [
  { label: '待认领', value: counts.value[STATUS_PENDING] ?? 0 },
  { label: '已认领', value: counts.value[STATUS_CLAIMED] ?? 0 },
  { label: '已移交', value: counts.value[STATUS_TRANSFERRED] ?? 0 },
  { label: '已报废', value: counts.value[STATUS_SCRAPPED] ?? 0 },
])
const pendingRows = computed(() => rows.value.filter((row) => row.status === STATUS_PENDING))
const allPendingSelected = computed(
  () => pendingRows.value.length > 0 && pendingRows.value.every((row) => selectedIds.value.includes(row.id)),
)
const batchSuccessCount = computed(() => batchResults.value.filter((item) => item.ok).length)
const batchFailureCount = computed(() => batchResults.value.length - batchSuccessCount.value)

function emptyFormValues() {
  return {
    物品类别: '',
    物品名称: '',
    物品特征: '',
    捡拾地点: '',
    捡拾日期: '',
    捡拾人: '',
    保管人: '',
    备注: '',
  }
}

function changeStatus(status: string) {
  activeStatus.value = status
  selectedIds.value = []
  void reload()
}

function resetFilters() {
  keyword.value = ''
  activeStatus.value = STATUS_PENDING
  selectedIds.value = []
  void reload()
}

function toggleRow(id: number) {
  batchHint.value = ''
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
  } else {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function toggleSelectAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  selectedIds.value = checked ? pendingRows.value.map((row) => row.id) : []
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  formModal.show = true
  formModal.mode = 'create'
  formModal.id = 0
  formModal.error = ''
  formModal.values = emptyFormValues()
}

function openEdit(row: Row) {
  formModal.show = true
  formModal.mode = 'edit'
  formModal.id = row.id
  formModal.error = ''
  formModal.values = {
    物品类别: row.物品类别 ?? '',
    物品名称: row.物品名称 ?? '',
    物品特征: row.物品特征 ?? '',
    捡拾地点: row.捡拾地点 ?? '',
    捡拾日期: row.捡拾日期 ?? '',
    捡拾人: row.捡拾人 ?? '',
    保管人: row.保管人 ?? '',
    备注: row.备注 ?? '',
  }
}

function closeForm() {
  formModal.show = false
}

async function submitForm() {
  formModal.error = ''
  const requiredMissing = ['物品类别', '捡拾地点', '保管人'].filter((field) => !formModal.values[field as keyof typeof formModal.values].trim())
  if (requiredMissing.length) {
    formModal.error = `请填写：${requiredMissing.join('、')}`
    return
  }
  const url = formModal.mode === 'create' ? ENDPOINT : `${ENDPOINT}/${formModal.id}`
  const response = await request(url, {
    method: formModal.mode === 'create' ? 'POST' : 'PUT',
    body: JSON.stringify({ values: { ...formModal.values } }),
  })
  const payload = (await response.json()) as ActionResponse
  if (!response.ok || !payload.ok) {
    formModal.error = payload.message || '保存失败'
    return
  }
  formModal.show = false
  await reload()
}

function openClaim(row: Row) {
  claimModal.show = true
  claimModal.row = row
  claimModal.error = ''
  claimModal.values = { 认领人: '', 证件号: '', 备注: '' }
}

function closeClaim() {
  claimModal.show = false
  claimModal.row = null
}

async function submitClaim() {
  if (!claimModal.row) return
  const claimedId = claimModal.row.id
  claimModal.error = ''
  if (!claimModal.values.认领人.trim() || !claimModal.values.证件号.trim()) {
    claimModal.error = '请填写认领人与证件号'
    return
  }
  const response = await request(`${ENDPOINT}/${claimModal.row.id}/claim`, {
    method: 'POST',
    body: JSON.stringify({ ...claimModal.values }),
  })
  const payload = (await response.json()) as ActionResponse
  if (!response.ok || !payload.ok) {
    claimModal.error = payload.message || '认领核销失败'
    return
  }
  closeClaim()
  selectedIds.value = selectedIds.value.filter((id) => id !== claimedId)
  await reload()
}

function openBatch(action: 'transfer' | 'scrap') {
  if (!selectedIds.value.length) {
    batchHint.value = '请先勾选待认领物品'
    return
  }
  openBatchDialog(action, [...selectedIds.value])
}

function openSingleBatch(row: Row, action: 'transfer' | 'scrap') {
  openBatchDialog(action, [row.id])
}

function openBatchDialog(action: 'transfer' | 'scrap', ids: number[]) {
  batchModal.show = true
  batchModal.action = action
  batchModal.ids = ids
  batchModal.error = ''
  batchModal.values = { 接收人: '', 移交地点: '', 报废原因: '', 备注: '' }
}

function closeBatch() {
  batchModal.show = false
  batchModal.ids = []
}

async function submitBatch() {
  batchModal.error = ''
  if (batchModal.action === 'transfer'
    && (!batchModal.values.接收人.trim() || !batchModal.values.移交地点.trim())) {
    batchModal.error = '请填写接收人与移交地点'
    return
  }
  if (batchModal.action === 'scrap' && !batchModal.values.报废原因.trim()) {
    batchModal.error = '请填写报废原因'
    return
  }
  const path = batchModal.action === 'transfer' ? '/transfer' : '/scrap'
  const response = await request(`${ENDPOINT}${path}`, {
    method: 'POST',
    body: JSON.stringify({ ids: batchModal.ids, ...batchModal.values }),
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({ detail: '批量处理失败' }))) as { detail?: string }
    batchModal.error = payload.detail || '批量处理失败'
    return
  }
  const payload = (await response.json()) as BatchResponse
  batchModal.show = false
  batchResults.value = payload.results
  selectedIds.value = []
  await reload()
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detailEntry.value = await fetchJson<Row>(`${ENDPOINT}/${row.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单条记录读取失败'
  }
}

async function loadCounts() {
  try {
    const payload = await fetchJson<{ items: Row[] }>(`${ENDPOINT}?size=200`)
    const nextCounts: Record<string, number> = {}
    for (const row of payload.items) {
      nextCounts[row.status] = (nextCounts[row.status] ?? 0) + 1
    }
    counts.value = nextCounts
  } catch {
    counts.value = {}
  }
}

async function reload() {
  errorMessage.value = ''
  batchHint.value = ''
  selectedIds.value = selectedIds.value.filter((id) => rows.value.find((row) => row.id === id)?.status === STATUS_PENDING)
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  const path = activeStatus.value === STATUS_PENDING
    ? `${ENDPOINT}/pending?${query.toString()}`
    : `${ENDPOINT}?${query.toString()}${activeStatus.value ? `${query.toString() ? '&' : ''}status=${encodeURIComponent(activeStatus.value)}` : ''}`
  try {
    const payload = await fetchJson<{ items: Row[]; total: number }>(path)
    rows.value = payload.items
    total.value = payload.total
    selectedIds.value = selectedIds.value.filter((id) => payload.items.some((row) => row.id === id))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '遗失物品列表读取失败'
  } finally {
    await loadCounts()
  }
}

onMounted(reload)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 16px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 13px;
}
.tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.inline-filter {
  display: flex;
  gap: 8px;
}
.inline-filter input {
  width: 260px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 10px;
  font-size: 13px;
}
.select-all {
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn.danger {
  color: #b42318;
  border-color: #f0a8a0;
}
.check-col {
  width: 48px;
  text-align: center;
}
.lost-table {
  table-layout: auto;
}
.lost-actions {
  flex-wrap: wrap;
  min-width: 180px;
}
.danger-link {
  color: #b42318;
}
.status-pending {
  color: var(--brand);
  font-weight: 600;
}
.muted-text {
  color: var(--muted);
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  padding: 20px;
}
.modal {
  width: min(760px, 100%);
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.detail-modal {
  width: min(820px, 100%);
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.modal-head h3 {
  margin: 0;
  font-size: 17px;
}
.modal-close {
  border: none;
  background: none;
  font-size: 22px;
  cursor: pointer;
  color: var(--muted);
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.single-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-grid label,
.single-form label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  color: var(--muted);
}
.form-grid label.required > span::after,
.single-form label.required > span::after {
  content: ' *';
  color: #b42318;
}
.form-grid input,
.form-grid textarea,
.single-form input,
.single-form textarea {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 9px;
  font: inherit;
  color: #1f2937;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
.modal-tip {
  font-size: 12px;
  color: var(--muted);
  margin: 10px 0 0;
}
.detail-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
  margin: 0;
}
.detail-list div {
  border-bottom: 1px solid #eef2f7;
  padding-bottom: 6px;
}
.detail-list dt {
  color: var(--muted);
  font-size: 12px;
}
.detail-list dd {
  margin: 3px 0 0;
  font-size: 13px;
}
.result-modal {
  width: min(640px, 100%);
}
.result-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-list li {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  display: flex;
  gap: 10px;
  font-size: 13px;
}
.result-ok {
  background: #f0fdf4;
}
.result-fail {
  background: #fef3f2;
}
.result-ok strong {
  color: #15803d;
}
.result-fail strong {
  color: #b42318;
}
</style>
