import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import sauApi from '@/api/sau'

export const useSauStore = defineStore('sau', () => {
  const schema = ref({})
  const schemaLoading = ref(false)
  const schemaLoaded = ref(false)

  const accounts = ref([])
  const accountsLoading = ref(false)

  const materials = ref([])
  const materialsLoading = ref(false)

  const tasks = ref([])
  const tasksLoading = ref(false)
  const activeTaskId = ref('')

  // 平台清单：{ key, label, help, actions: [...] }
  const platforms = computed(() =>
    Object.entries(schema.value)
      .map(([key, info]) => ({
        key,
        label: info.label || key,
        help: info.help || '',
        actions: Object.keys(info.actions || {})
      }))
      .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN'))
  )

  const platformMap = computed(() => {
    const map = {}
    for (const item of platforms.value) {
      map[item.key] = item
    }
    return map
  })

  function platformLabel(key) {
    return (platformMap.value[key] && platformMap.value[key].label) || key
  }

  function actionSchema(platform, action) {
    const info = schema.value[platform]
    if (!info || !info.actions) return null
    return info.actions[action] || null
  }

  async function loadSchema(force = false) {
    if (schemaLoaded.value && !force) return schema.value
    schemaLoading.value = true
    try {
      const data = await sauApi.getSchema()
      schema.value = data || {}
      schemaLoaded.value = true
      return schema.value
    } finally {
      schemaLoading.value = false
    }
  }

  async function loadAccounts() {
    accountsLoading.value = true
    try {
      const data = await sauApi.listAccounts()
      accounts.value = data || []
      return accounts.value
    } finally {
      accountsLoading.value = false
    }
  }

  async function loadMaterials() {
    materialsLoading.value = true
    try {
      const data = await sauApi.listMaterials()
      materials.value = data || []
      return materials.value
    } finally {
      materialsLoading.value = false
    }
  }

  async function loadTasks(limit = 50) {
    tasksLoading.value = true
    try {
      const data = await sauApi.listTasks(limit)
      tasks.value = data || []
      return tasks.value
    } finally {
      tasksLoading.value = false
    }
  }

  // 该平台已登录的账号名列表
  function accountsFor(platform) {
    return accounts.value.filter((item) => item.platform === platform)
  }

  return {
    schema,
    schemaLoading,
    schemaLoaded,
    accounts,
    accountsLoading,
    materials,
    materialsLoading,
    tasks,
    tasksLoading,
    activeTaskId,
    platforms,
    platformMap,
    platformLabel,
    actionSchema,
    loadSchema,
    loadAccounts,
    loadMaterials,
    loadTasks,
    accountsFor
  }
})

export default useSauStore
