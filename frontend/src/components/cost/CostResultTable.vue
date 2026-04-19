<template>
  <a-card title="估算结果" :bordered="false">
    <template #extra>
      <a-space>
        <a-tag color="blue">v{{ estimate.version }}</a-tag>
        <a-tag :color="estimate.status === 'completed' ? 'green' : 'orange'">
          {{ estimate.status === 'completed' ? '已完成' : '计算中' }}
        </a-tag>
        <a-button size="small" :loading="recalculating" @click="handleRecalculate">
          重新计算
        </a-button>
      </a-space>
    </template>

    <a-row :gutter="16" style="margin-bottom: 20px">
      <a-col :span="8">
        <a-statistic title="工程总造价" :value="estimate.total_cost" prefix="¥" :precision="2" />
      </a-col>
      <a-col :span="8" v-if="estimate.cost_per_km">
        <a-statistic title="每公里造价" :value="estimate.cost_per_km" prefix="¥" :precision="2" />
      </a-col>
      <a-col :span="8">
        <a-statistic title="工程类型" :value="estimate.project_type" />
      </a-col>
    </a-row>

    <a-tabs>
      <a-tab-pane key="summary" tab="分类汇总">
        <a-table
          :columns="summaryColumns"
          :data-source="estimate.summary"
          :pagination="false"
          row-key="category"
          size="small"
        />
      </a-tab-pane>

      <a-tab-pane key="details" tab="分项明细">
        <a-table
          :columns="detailColumns"
          :data-source="estimate.details"
          :pagination="{ pageSize: 10 }"
          :row-key="(record: CostEstimateItem, index: number) => record.item + '-' + index"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'subtotal'">
              ¥{{ record.subtotal.toFixed(2) }}
            </template>
            <template v-if="column.key === 'unit_price'">
              ¥{{ record.unit_price.toFixed(2) }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="params" tab="设计参数">
        <a-descriptions :column="3" bordered size="small">
          <a-descriptions-item
            v-for="(value, key) in estimate.design_params"
            :key="String(key)"
            :label="String(key)"
          >
            {{ value }}
          </a-descriptions-item>
        </a-descriptions>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { costEstimationApi, type CostEstimate, type CostEstimateItem } from '@/api/cost_estimation'

const props = defineProps<{ estimate: CostEstimate; projectId: string }>()
const emit = defineEmits<{ recalculated: [estimate: CostEstimate] }>()

const recalculating = ref(false)

const summaryColumns = [
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '工程量', dataIndex: 'total_quantity', key: 'total_quantity' },
  { title: '金额 (¥)', dataIndex: 'total_amount', key: 'total_amount', customRender: ({ text }: { text: number }) => `¥${text.toFixed(2)}` },
]

const detailColumns = [
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '项目', dataIndex: 'item', key: 'item' },
  { title: '工程量', dataIndex: 'quantity', key: 'quantity' },
  { title: '单位', dataIndex: 'unit', key: 'unit' },
  { title: '单价', key: 'unit_price' },
  { title: '金额', key: 'subtotal' },
]

async function handleRecalculate() {
  recalculating.value = true
  try {
    const updated = (await costEstimationApi.recalculate(props.projectId, props.estimate.id)).data
    emit('recalculated', updated)
    message.success('重新计算完成')
  } catch {
    message.error('重新计算失败')
  } finally {
    recalculating.value = false
  }
}
</script>
