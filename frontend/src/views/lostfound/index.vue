<template>
  <section class="page" data-module="lostfound">
    <header class="page-head">
      <div>
        <h2>遗失物品管理</h2>
        <p class="page-desc">受理捡拾记录并维护失物招领信息（物品类别、捡拾地点、保管人）；旅客认领时登记认领人与证件号，核销后退出待认领清单。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">受理捡拾记录</button>
        <button class="btn" type="button" @click="exportRows">导出遗失物品清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="scope-tabs">
      <button
        v-for="tab in scopeTabs"
        :key="tab.value"
        type="button"
        :class="['scope-tab', { active: scope === tab.value }]"
        @click="switchScope(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按登记编号/物品名称/保管人检索" />
      </label>
      <label v-if="scope === 'all'" class="filter-item">
        <span>状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div class="bulk-bar">
      <span class="bulk-tip">已选 <strong>{{ selectedIds.length }}</strong> 条（仅「待认领」记录可移交/报废）</span>
      <button class="btn" type="button" :disabled="!selectedIds.length" @click="openBatch('批量移交')">批量移交</button>
      <button class="btn danger" type="button" :disabled="!selectedIds.length" @click="openBatch('批量报废')">批量报废</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th class="col-check"><input type="checkbox" :checked="allChecked" :indeterminate.prop="someChecked" @change="toggleAll" /></th>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ selected: selectedIds.includes(Number(row.id)) }">
          <td class="col-check">
            <input
              type="checkbox"
              :value="Number(row.id)"
              v-model="selectedIds"
              :disabled="!isBatchable(row)"
              :title="isBatchable(row) ? '' : '仅待认领记录可批量移交/报废'"
            />
          </td>
          <td v-for="column in columns" :key="column">
            <span v-if="column === '状态'" :class="['status-badge', badgeClass(row.status)]">{{ row[column] }}</span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(Number(row.id))">查看明细</button>
            <button v-if="row.status === '待认领'" class="link" type="button" @click="openClaim(Number(row.id))">登记认领</button>
            <button v-if="row.status === '待核销'" class="link" type="button" @click="verifyClaim(Number(row.id))">认领核销</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条遗失物品记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 受理捡拾记录 -->
    <div v-if="dialog === 'create'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>受理捡拾记录</h3>
        <div v-for="field in createFields" :key="field.name" class="form-row">
          <label><span>{{ field.label }}<em v-if="field.required">*</em></span></label>
          <input
            v-if="field.type !== 'textarea'"
            v-model="createForm[field.name]"
            :type="field.type || 'text'"
            :placeholder="`请输入${field.label}`"
          />
          <textarea v-else v-model="createForm[field.name]" rows="2" :placeholder="`请输入${field.label}`" />
        </div>
        <div class="form-row">
          <label><span>物品类别<em>*</em></span></label>
          <select v-model="createForm['物品类别']">
            <option value="">请选择物品类别</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">确认受理</button>
        </div>
      </div>
    </div>

    <!-- 登记认领 -->
    <div v-if="dialog === 'claim'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>登记旅客认领 · {{ activeId }}</h3>
        <div class="form-row">
          <label><span>认领人<em>*</em></span></label>
          <input v-model="claimForm.认领人" placeholder="请输入认领人姓名" />
        </div>
        <div class="form-row">
          <label><span>证件号<em>*</em></span></label>
          <input v-model="claimForm.证件号" placeholder="请输入身份证/护照等证件号码" />
        </div>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" @click="submitClaim">登记并待核销</button>
        </div>
      </div>
    </div>

    <!-- 批量移交 -->
    <div v-if="dialog === 'batchHand'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>批量移交（{{ selectedIds.length }} 条）</h3>
        <div class="form-row">
          <label><span>移交去向<em>*</em></span></label>
          <input v-model="batchForm.移交去向" placeholder="如：机场公安失物管理科" />
        </div>
        <p class="form-hint">将逐条校验，未通过的记录会被跳过，其余记录继续处理。</p>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" @click="submitBatch('批量移交')">确认移交</button>
        </div>
      </div>
    </div>

    <!-- 批量报废 -->
    <div v-if="dialog === 'batchScrap'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>批量报废（{{ selectedIds.length }} 条）</h3>
        <div class="form-row">
          <label><span>报废原因</span></label>
          <textarea v-model="batchForm.报废原因" rows="2" placeholder="如：物品破损无法继续保管，按规定报废" />
        </div>
        <p class="form-hint">将逐条校验，未通过的记录会被跳过，其余记录继续处理。</p>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn danger" type="button" @click="submitBatch('批量报废')">确认报废</button>
        </div>
      </div>
    </div>

    <!-- 单条移交/报废（明细内） -->
    <div v-if="dialog === 'hand' || dialog === 'scrap'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>{{ dialog === 'hand' ? '移交物品' : '报废物品' }} · {{ activeId }}</h3>
        <div v-if="dialog === 'hand'" class="form-row">
          <label><span>移交去向<em>*</em></span></label>
          <input v-model="singleForm.移交去向" placeholder="如：机场公安失物管理科" />
        </div>
        <div v-else class="form-row">
          <label><span>报废原因</span></label>
          <textarea v-model="singleForm.报废原因" rows="2" placeholder="请填写报废原因" />
        </div>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button
            :class="['btn', dialog === 'hand' ? 'primary' : 'danger']"
            type="button"
            @click="submitSingle(dialog === 'hand' ? '移交' : '报废')"
          >
            确认
          </button>
        </div>
      </div>
    </div>

    <!-- 批量处理结果 -->
    <div v-if="dialog === 'batchResult' && batchResult" class="modal-mask" @click.self="closeDialog">
      <div class="modal wide">
        <h3>{{ batchResult.action }}处理结果</h3>
        <p class="form-hint">
          共 {{ batchResult.total }} 条，成功 {{ batchResult.success }} 条，
          <span :class="{ 'error-text': batchResult.failed > 0 }">未通过 {{ batchResult.failed }} 条（已跳过）</span>
        </p>
        <table class="data-table result-table">
          <thead>
            <tr><th>登记编号</th><th>物品名称</th><th>结果</th><th>说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in batchResult.items" :key="item.id">
              <td>{{ resultName(item) }}</td>
              <td>{{ resultItemName(item) }}</td>
              <td>
                <span :class="['status-badge', item.ok ? 'badge-done' : 'badge-fail']">
                  {{ item.ok ? '已处理' : '已跳过' }}
                </span>
              </td>
              <td>{{ item.message }}</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-foot">
          <button class="btn primary" type="button" @click="closeDialog">知道了</button>
        </div>
      </div>
    </div>

    <!-- 单条明细 -->
    <div v-if="dialog === 'detail' && detail" class="modal-mask" @click.self="closeDialog">
      <div class="modal wide">
        <h3>物品明细 · {{ detail['登记编号'] }}</h3>
        <p class="detail-status">
          当前状态：<span :class="['status-badge', badgeClass(detail.status)]">{{ detail.status }}</span>
        </p>
        <dl class="detail-grid">
          <div v-for="f in detailFields" :key="f" class="detail-cell">
            <dt>{{ f }}</dt>
            <dd>{{ detail[f] || '—' }}</dd>
          </div>
        </dl>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeDialog">关闭</button>
          <template v-if="detail.status === '待认领'">
            <button class="btn" type="button" @click="openHandFromDetail">移交</button>
            <button class="btn danger" type="button" @click="openScrapFromDetail">报废</button>
            <button class="btn primary" type="button" @click="openClaim(Number(detail.id))">登记认领</button>
          </template>
          <button v-else-if="detail.status === '待核销'" class="btn primary" type="button" @click="verifyClaim(Number(detail.id))">认领核销</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

interface BatchResultItem {
  id: number
  ok: boolean
  message: string
  entry: Row | null
}
interface BatchResult {
  ok: boolean
  action: string
  total: number
  success: number
  failed: number
  items: BatchResultItem[]
}

const ENDPOINT = '/api/lostfound'
const columns = ['登记编号', '物品名称', '物品类别', '捡拾地点', '捡拾日期', '保管人', '认领人', '证件号', '状态']
const detailFields = ['物品名称', '物品类别', '捡拾地点', '捡拾日期', '保管人', '捡拾经过', '认领人', '证件号', '移交去向', '移交时间', '报废原因', '报废时间']
const statuses = ['待认领', '待核销', '已移交', '已报废', '已认领']
const categories = ['电子产品', '箱包', '现金证件', '衣物', '书籍文件', '首饰', '其他']
const scopeTabs = [
  { value: 'waiting', label: '待认领清单' },
  { value: 'all', label: '全部记录' },
] as const

const createFields: { name: string; label: string; required?: boolean; type?: string }[] = [
  { name: '物品名称', label: '物品名称', required: true },
  { name: '捡拾地点', label: '捡拾地点', required: true },
  { name: '捡拾日期', label: '捡拾日期', type: 'date' },
  { name: '保管人', label: '保管人', required: true },
  { name: '捡拾经过', label: '捡拾经过', type: 'textarea' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const scope = ref<'waiting' | 'all'>('waiting')
const selectedIds = ref<number[]>([])

const stats = ref([
  { label: '待认领', value: 0 },
  { label: '待核销', value: 0 },
  { label: '已认领', value: 0 },
  { label: '已移交/报废', value: 0 },
])

type DialogKind = '' | 'create' | 'claim' | 'batchHand' | 'batchScrap' | 'hand' | 'scrap' | 'batchResult' | 'detail'
const dialog = ref<DialogKind>('')
const dialogError = ref('')
const activeId = ref<number | null>(null)
const detail = ref<Row | null>(null)
const batchResult = ref<BatchResult | null>(null)
const claimFromDetail = ref(false)

const today = () => new Date().toISOString().slice(0, 10)
const emptyCreateForm = () => ({ 物品名称: '', 物品类别: '', 捡拾地点: '', 捡拾日期: today(), 保管人: '', 捡拾经过: '' })
const createForm = reactive<Record<string, string>>(emptyCreateForm())
const claimForm = reactive({ 认领人: '', 证件号: '' })
const batchForm = reactive({ 移交去向: '', 报废原因: '' })
const singleForm = reactive({ 移交去向: '', 报废原因: '' })

const emptyText = computed(() => (scope.value === 'waiting' ? '待认领清单暂无记录' : '暂无遗失物品记录，可先受理捡拾记录'))
const batchableRows = computed(() => rows.value.filter(isBatchable))
const allChecked = computed(() => batchableRows.value.length > 0 && batchableRows.value.every((r) => selectedIds.value.includes(Number(r.id))))
const someChecked = computed(() => !allChecked.value && selectedIds.value.length > 0)

function isBatchable(row: Row): boolean {
  return row.status === '待认领'
}

function badgeClass(status: string | number | boolean | null | undefined): string {
  switch (status) {
    case '待认领':
      return 'badge-waiting'
    case '待核销':
      return 'badge-claim'
    case '已认领':
      return 'badge-done'
    case '已移交':
    case '已报废':
      return 'badge-off'
    default:
      return 'badge-waiting'
  }
}

function switchScope(value: 'waiting' | 'all') {
  scope.value = value
  selectedIds.value = []
  void reload()
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  selectedIds.value = checked ? batchableRows.value.map((r) => Number(r.id)) : []
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function closeDialog() {
  dialog.value = ''
  dialogError.value = ''
  activeId.value = null
  detail.value = null
  batchResult.value = null
  claimFromDetail.value = false
}

function openCreate() {
  Object.assign(createForm, emptyCreateForm())
  dialogError.value = ''
  dialog.value = 'create'
}

function openClaim(id: number) {
  activeId.value = id
  claimForm.认领人 = ''
  claimForm.证件号 = ''
  dialogError.value = ''
  // 从明细弹窗进入时，认领登记成功后回到明细并刷新为「待核销」
  claimFromDetail.value = dialog.value === 'detail'
  dialog.value = 'claim'
}

function openBatch(action: string) {
  if (!selectedIds.value.length) return
  batchForm.移交去向 = ''
  batchForm.报废原因 = ''
  dialogError.value = ''
  dialog.value = action === '批量移交' ? 'batchHand' : 'batchScrap'
}

function openHandFromDetail() {
  activeId.value = detail.value ? Number(detail.value.id) : null
  singleForm.移交去向 = ''
  dialogError.value = ''
  dialog.value = 'hand'
}

function openScrapFromDetail() {
  activeId.value = detail.value ? Number(detail.value.id) : null
  singleForm.报废原因 = ''
  dialogError.value = ''
  dialog.value = 'scrap'
}

async function submitCreate() {
  dialogError.value = ''
  try {
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values: { ...createForm } }) })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message || '捡拾记录受理失败'
      return
    }
    closeDialog()
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '捡拾记录受理失败'
  }
}

async function submitClaim() {
  if (activeId.value === null) return
  dialogError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${activeId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '登记认领', ...claimForm } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message || '认领登记失败'
      return
    }
    const backToDetail = claimFromDetail.value
    closeDialog()
    if (backToDetail && payload.entry) {
      // 明细与列表共用后端同一份状态：重新拉取即可看到「待核销」
      detail.value = payload.entry as Row
      activeId.value = Number(payload.entry.id)
      dialog.value = 'detail'
    }
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '认领登记失败'
  }
}

async function verifyClaim(id: number) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '认领核销' } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      errorMessage.value = payload.message || '认领核销失败'
      return
    }
    selectedIds.value = selectedIds.value.filter((sid) => sid !== id)
    // 若正在查看该件明细，同步刷新为「已认领」，列表也随之退出待认领清单
    if (dialog.value === 'detail' && detail.value && Number(detail.value.id) === id) {
      detail.value = payload.entry as Row
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '认领核销失败'
  }
}

async function submitSingle(action: string) {
  if (activeId.value === null) return
  dialogError.value = ''
  const values = action === '移交' ? { action, 移交去向: singleForm.移交去向 } : { action, 报废原因: singleForm.报废原因 }
  try {
    const response = await request(`${ENDPOINT}/${activeId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message || `${action}失败`
      return
    }
    closeDialog()
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : `${action}失败`
  }
}

async function submitBatch(action: string) {
  dialogError.value = ''
  if (action === '批量移交' && !batchForm.移交去向.trim()) {
    dialogError.value = '请填写移交去向'
    return
  }
  const values = action === '批量移交' ? { 移交去向: batchForm.移交去向.trim() } : { 报废原因: batchForm.报废原因.trim() }
  try {
    const response = await request(`${ENDPOINT}/batch/actions`, {
      method: 'POST',
      body: JSON.stringify({ action, ids: selectedIds.value, values }),
    })
    const payload = await response.json()
    if (!response.ok) {
      dialogError.value = payload.detail || '批量处理失败'
      return
    }
    batchResult.value = payload as BatchResult
    dialog.value = 'batchResult'
    selectedIds.value = []
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '批量处理失败'
  }
}

async function openDetail(id: number) {
  dialogError.value = ''
  activeId.value = id
  dialog.value = 'detail'
  detail.value = null
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (!response.ok) {
      dialogError.value = '明细读取失败'
      return
    }
    detail.value = await response.json()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '明细读取失败'
  }
}

function resultName(item: BatchResultItem): string {
  return item.entry ? String(item.entry['登记编号'] ?? `#${item.id}`) : `#${item.id}`
}

function resultItemName(item: BatchResultItem): string {
  return item.entry ? String(item.entry['物品名称'] ?? '—') : '—'
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?page=1&size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const all = (payload.items ?? []) as Row[]
    const count = (s: string) => all.filter((r) => r.status === s).length
    stats.value[0].value = count('待认领')
    stats.value[1].value = count('待核销')
    stats.value[2].value = count('已认领')
    stats.value[3].value = count('已移交') + count('已报废')
  } catch {
    // 统计失败不阻塞列表使用
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (scope.value === 'waiting') {
    params.set('waiting', 'true')
  } else if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('遗失物品列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 清理已不在待认领状态的勾选项，保持勾选与状态一致
    selectedIds.value = selectedIds.value.filter((id) =>
      rows.value.some((r) => Number(r.id) === id && isBatchable(r)),
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '遗失物品列表读取失败'
  }
  await loadStats()
}

onMounted(reload)
</script>

<style scoped>
.scope-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.scope-tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
  color: var(--muted);
}
.scope-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 10px;
  font-size: 13px;
}
.bulk-tip {
  color: var(--muted);
  flex: 1;
}
.bulk-tip strong {
  color: var(--brand);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.danger {
  border-color: #d92d20;
  color: #b42318;
  background: #fff;
}
.btn.danger:not(:disabled):hover {
  background: #fef3f2;
}
.col-check {
  width: 36px;
  text-align: center;
}
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  white-space: nowrap;
}
.badge-waiting {
  background: #fff4de;
  color: #b54708;
}
.badge-claim {
  background: #e0efff;
  color: #175cd3;
}
.badge-done {
  background: #dcfae6;
  color: #067647;
}
.badge-off {
  background: #f2f4f7;
  color: #667085;
}
.badge-fail {
  background: #fef3f2;
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  width: 420px;
  max-height: 86vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.modal.wide {
  width: 640px;
}
.modal h3 {
  margin: 0 0 14px;
  font-size: 16px;
}
.form-row {
  margin-bottom: 10px;
}
.form-row label span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-row em {
  color: #d92d20;
  font-style: normal;
  margin-left: 2px;
}
.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  font-family: inherit;
}
.form-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 6px 0;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.result-table {
  margin-top: 8px;
}
.detail-status {
  font-size: 13px;
  margin: 0 0 10px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  margin: 0;
}
.detail-cell {
  border-bottom: 1px dashed var(--border);
  padding-bottom: 4px;
}
.detail-cell dt {
  font-size: 12px;
  color: var(--muted);
}
.detail-cell dd {
  margin: 2px 0 0;
  font-size: 13px;
  word-break: break-all;
}
tr.selected {
  background: #f5f9ff;
}
</style>
