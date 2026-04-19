import { defineStore } from 'pinia'
import { ref } from 'vue'
import { projectsApi, type Project, type CreateProjectRequest } from '@/api/projects'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const total = ref(0)
  const loading = ref(false)

  async function fetchProjects(skip = 0, limit = 20) {
    loading.value = true
    try {
      const res = await projectsApi.list(skip, limit)
      projects.value = res.data.projects
      total.value = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function createProject(data: CreateProjectRequest): Promise<Project> {
    const res = await projectsApi.create(data)
    await fetchProjects()
    return res.data
  }

  async function deleteProject(id: string) {
    await projectsApi.delete(id)
    await fetchProjects()
  }

  return { projects, total, loading, fetchProjects, createProject, deleteProject }
})
