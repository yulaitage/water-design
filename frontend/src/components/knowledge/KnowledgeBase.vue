<template>
  <div class="knowledge-panel">
    <a-card :bordered="false">
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="specifications" tab="规范管理">
          <div style="margin-bottom: 16px">
            <a-button type="primary" size="small" @click="showSpecForm = true">新增规范</a-button>
          </div>
          <a-table
            :columns="specColumns"
            :data-source="specifications"
            :loading="specsLoading"
            :pagination="{ pageSize: 10 }"
            row-key="id"
            size="small"
          />
        </a-tab-pane>

        <a-tab-pane key="cases" tab="案例管理">
          <div style="margin-bottom: 16px">
            <a-button type="primary" size="small" @click="showCaseForm = true">新增案例</a-button>
          </div>
          <a-table
            :columns="caseColumns"
            :data-source="cases"
            :loading="casesLoading"
            :pagination="{ pageSize: 10 }"
            row-key="id"
            size="small"
          />
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <a-modal v-model:open="showSpecForm" title="新增规范条文" ok-text="提交" cancel-text="取消" @ok="handleAddSpec">
      <a-form layout="vertical">
        <a-form-item label="规范名称" required>
          <a-input v-model:value="specForm.name" placeholder="如：堤防工程设计规范" />
        </a-form-item>
        <a-form-item label="规范编号" required>
          <a-input v-model:value="specForm.code" placeholder="如：GB 50286" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="章节">
              <a-input v-model:value="specForm.chapter" placeholder="3.1" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="条号">
              <a-input v-model:value="specForm.section" placeholder="3.1.2" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="适用工程类型">
          <a-select v-model:value="specForm.project_types" mode="tags" placeholder="如：堤防、河道整治">
            <a-select-option value="堤防">堤防</a-select-option>
            <a-select-option value="河道整治">河道整治</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="条文内容" required>
          <a-textarea v-model:value="specForm.content" :rows="4" placeholder="规范条文内容" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="showCaseForm" title="新增工程案例" ok-text="提交" cancel-text="取消" @ok="handleAddCase">
      <a-form layout="vertical">
        <a-form-item label="案例名称" required>
          <a-input v-model:value="caseForm.name" placeholder="如：长江荆江河段整治工程" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="工程类型">
              <a-select v-model:value="caseForm.project_type">
                <a-select-option value="堤防">堤防</a-select-option>
                <a-select-option value="河道整治">河道整治</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="所在地区">
              <a-input v-model:value="caseForm.location" placeholder="省/市" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="业主单位">
          <a-input v-model:value="caseForm.owner" placeholder="建设单位" />
        </a-form-item>
        <a-form-item label="案例摘要" required>
          <a-textarea v-model:value="caseForm.summary" :rows="4" placeholder="工程案例的主要内容摘要" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { knowledgeApi, type Specification, type Case } from '@/api/knowledge'

const activeTab = ref('specifications')
const specifications = ref<Specification[]>([])
const cases = ref<Case[]>([])
const specsLoading = ref(false)
const casesLoading = ref(false)

const showSpecForm = ref(false)
const showCaseForm = ref(false)

const specForm = reactive({
  name: '',
  code: '',
  chapter: '',
  section: '',
  content: '',
  project_types: [] as string[],
})

const caseForm = reactive({
  name: '',
  project_type: '堤防',
  location: '',
  owner: '',
  summary: '',
  design_params: {} as Record<string, unknown>,
})

const specColumns = [
  { title: '编号', dataIndex: 'code', key: 'code', width: 120, ellipsis: true },
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '章节', dataIndex: 'chapter', key: 'chapter', width: 80 },
  { title: '条号', dataIndex: 'section', key: 'section', width: 80 },
]

const caseColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '类型', dataIndex: 'project_type', key: 'project_type', width: 100 },
  { title: '地区', dataIndex: 'location', key: 'location', width: 120 },
  { title: '业主', dataIndex: 'owner', key: 'owner', width: 140, ellipsis: true },
]

async function loadSpecs() {
  specsLoading.value = true
  try {
    specifications.value = (await knowledgeApi.listSpecifications()).data
  } finally {
    specsLoading.value = false
  }
}

async function loadCases() {
  casesLoading.value = true
  try {
    cases.value = (await knowledgeApi.listCases()).data
  } finally {
    casesLoading.value = false
  }
}

async function handleAddSpec() {
  try {
    await knowledgeApi.addSpecification({
      name: specForm.name,
      code: specForm.code,
      chapter: specForm.chapter,
      section: specForm.section || null,
      content: specForm.content,
      project_types: specForm.project_types,
    })
    message.success('规范添加成功')
    showSpecForm.value = false
    specForm.name = ''
    specForm.code = ''
    specForm.chapter = ''
    specForm.section = ''
    specForm.content = ''
    specForm.project_types = []
    loadSpecs()
  } catch {
    message.error('添加失败')
  }
}

async function handleAddCase() {
  try {
    await knowledgeApi.addCase({
      name: caseForm.name,
      project_type: caseForm.project_type,
      location: caseForm.location,
      owner: caseForm.owner,
      summary: caseForm.summary || null,
      design_params: caseForm.design_params,
    })
    message.success('案例添加成功')
    showCaseForm.value = false
    caseForm.name = ''
    caseForm.location = ''
    caseForm.owner = ''
    caseForm.summary = ''
    loadCases()
  } catch {
    message.error('添加失败')
  }
}

onMounted(() => {
  loadSpecs()
  loadCases()
})
</script>

<style scoped>
.knowledge-panel {
  max-width: 900px;
}
</style>
