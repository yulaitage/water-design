<template>
  <div class="cost-panel">
    <a-card title="费用估算" :bordered="false">
      <a-form layout="vertical" @finish="handleEstimate">
        <a-form-item label="工程类型" name="project_type">
          <a-radio-group v-model:value="form.project_type">
            <a-radio-button value="堤防">堤防工程</a-radio-button>
            <a-radio-button value="河道整治">河道整治</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-divider orientation="left" style="font-size: 14px">设计参数</a-divider>

        <template v-if="form.project_type === '堤防'">
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="堤防长度 (km)">
                <a-input-number v-model:value="form.design_params.length" :min="0.1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="设计堤高 (m)">
                <a-input-number v-model:value="form.design_params.height" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="堤顶宽度 (m)">
                <a-input-number v-model:value="form.design_params.crest_width" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="迎水坡比">
                <a-input-number v-model:value="form.design_params.upstream_slope" :min="1" :max="10" step="0.5" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="背水坡比">
                <a-input-number v-model:value="form.design_params.downstream_slope" :min="1" :max="10" step="0.5" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="防洪标准 (年)">
                <a-input-number v-model:value="form.design_params.flood_standard" :min="5" step="5" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <template v-else>
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="河道长度 (km)">
                <a-input-number v-model:value="form.design_params.length" :min="0.1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="设计河宽 (m)">
                <a-input-number v-model:value="form.design_params.river_width" :min="10" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="设计水深 (m)">
                <a-input-number v-model:value="form.design_params.water_depth" :min="0.5" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="estimating">
            开始估算
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <CostResultTable
      v-if="currentEstimate"
      :estimate="currentEstimate"
      :project-id="projectId"
      @recalculated="onRecalculated"
      style="margin-top: 16px"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import CostResultTable from './CostResultTable.vue'
import { costEstimationApi, type CostEstimate } from '@/api/cost_estimation'

const props = defineProps<{ projectId: string }>()

const estimating = ref(false)
const currentEstimate = ref<CostEstimate | null>(null)

const form = reactive({
  project_type: '堤防' as '堤防' | '河道整治',
  design_params: {
    length: 5,
    height: 4,
    crest_width: 6,
    upstream_slope: 3,
    downstream_slope: 2.5,
    flood_standard: 20,
    river_width: 50,
    water_depth: 3,
  },
})

async function handleEstimate() {
  estimating.value = true
  try {
    const params: Record<string, number> = {}
    for (const [key, val] of Object.entries(form.design_params)) {
      if (val != null && val > 0) {
        params[key] = val
      }
    }
    if (Object.keys(params).length < 2) {
      message.warning('请至少填写两个设计参数')
      return
    }
    currentEstimate.value = (await costEstimationApi.create(props.projectId, {
      project_type: form.project_type,
      design_params: params,
    })).data
    message.success('估算完成')
  } catch {
    message.error('估算失败')
  } finally {
    estimating.value = false
  }
}

function onRecalculated(estimate: CostEstimate) {
  currentEstimate.value = estimate
}
</script>

<style scoped>
.cost-panel {
  max-width: 960px;
}
</style>
