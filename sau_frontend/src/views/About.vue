<template>
  <div class="about-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header"><span>关于</span></div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="项目">social-auto-upload</el-descriptions-item>
        <el-descriptions-item label="Web 版本">v2（argparse 自省驱动）</el-descriptions-item>
        <el-descriptions-item label="后端入口">sau_server.py（Flask）</el-descriptions-item>
        <el-descriptions-item label="CLI 入口">sau_cli.py</el-descriptions-item>
        <el-descriptions-item label="工作目录">{{ health.root || '-' }}</el-descriptions-item>
        <el-descriptions-item label="平台数量">{{ store.platforms.length }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>这套界面的工作原理</h4>
      <ul class="tips">
        <li>后端读取 <code>sau_cli.build_parser()</code> 的 argparse 定义，生成 <code>/api/schema</code>。</li>
        <li>前端按字段的 <code>kind</code> 自动渲染控件，CLI 新增参数时界面会自动出现。</li>
        <li>提交表单后，后端把字段拼回命令行，用独立子进程执行 <code>python -m sau_cli ...</code>。</li>
        <li>任务日志从子进程 stdout 实时收集，前端轮询显示，可随时取消（taskkill）。</li>
        <li>账号 = <code>cookies/&lt;platform&gt;_&lt;account&gt;.json</code>；素材 = <code>videos/</code> 下的文件。</li>
      </ul>

      <el-divider />

      <h4>命令行等价用法</h4>
      <pre class="cmd">cd E:\claude工作区\social-auto-upload
.\.venv\Scripts\sau.exe douyin login --account creator
.\.venv\Scripts\sau.exe douyin upload-video --account creator --file videos\demo.mp4 --title "标题"</pre>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const health = ref({})

onMounted(async () => {
  await store.loadSchema()
  try {
    health.value = await sauApi.getHealth()
  } catch {
    health.value = {}
  }
})
</script>

<style scoped>
.card-header {
  font-weight: 600;
}
.tips {
  padding-left: 18px;
  font-size: 13px;
  line-height: 2;
  color: #606266;
}
.tips code,
pre code {
  padding: 1px 5px;
  background: #f5f7fa;
  border-radius: 3px;
  font-family: Consolas, Monaco, monospace;
}
.cmd {
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.7;
  overflow-x: auto;
}
</style>
