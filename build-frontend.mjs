// 跨平台构建前端（供 tauri.conf.json 的 beforeBuildCommand 调用）
import { spawn } from 'node:child_process'
import path from 'node:path'

const root = path.dirname(process.argv[1])
const frontend = path.join(root, 'frontend')

const isWin = process.platform === 'win32'
const cmd = isWin ? 'npm.cmd' : 'npm'

const child = spawn(cmd, ['run', 'build'], {
  cwd: frontend,
  stdio: 'inherit',
  shell: isWin,
})

child.on('exit', (code) => process.exit(code ?? 0))
