// 跳板机配置区：档案下拉 + 增删 + 主机/端口/用户/密码 + 测试连接

import { useEffect, useState } from 'react'
import { api, type JumphostInput, type Profile } from '../ipc'
import { useApp } from '../stores'

interface Props {
  onJumphostChange?: (j: JumphostInput | null) => void
}

export function JumphostPanel({ onJumphostChange }: Props) {
  const { config, setConfig, addLog } = useApp()
  const [host, setHost] = useState('')
  const [port, setPort] = useState('22')
  const [user, setUser] = useState('')
  const [pwd, setPwd] = useState('')
  const [pwdVisible, setPwdVisible] = useState(false)
  const [testing, setTesting] = useState(false)

  const profiles = config.profiles

  // 挂载时加载上次选中的档案，否则输入框为空、无法启动隧道
  useEffect(() => {
    if (config.lastProfile) {
      loadProfile(config.lastProfile)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 输入变化时上报给 App（供「全部启动」与每行启动使用）
  useEffect(() => {
    const portNum = parseInt(port.trim() || '22', 10)
    if (host.trim() && user.trim() && !Number.isNaN(portNum)) {
      onJumphostChange?.({
        host: host.trim(),
        port: portNum,
        username: user.trim(),
        password: pwd,
      })
    } else {
      onJumphostChange?.(null)
    }
  }, [host, port, user, pwd, onJumphostChange])

  const loadProfile = (name: string) => {
    const p = profiles.find((x) => x.name === name)
    if (!p) return
    setHost(p.host)
    setPort(String(p.port))
    setUser(p.username)
    setPwd(p.password)
  }

  const onProfileChange = (name: string) => {
    loadProfile(name)
    const next = { ...config, lastProfile: name }
    setConfig(next)
    void api.setLastProfile(name)
  }

  const readJumphost = (): JumphostInput | null => {
    if (!host.trim() || !user.trim()) {
      alert('请填写跳板机的主机和用户名')
      return null
    }
    const portNum = parseInt(port.trim() || '22', 10)
    if (Number.isNaN(portNum)) {
      alert('跳板机端口必须是整数')
      return null
    }
    return { host: host.trim(), port: portNum, username: user.trim(), password: pwd }
  }

  const saveAsNew = async () => {
    const data = readJumphost()
    if (!data) return
    const name = window.prompt('请输入档案名称：')
    if (!name) return
    if (profiles.some((p) => p.name === name) && !window.confirm(`档案「${name}」已存在，是否覆盖？`)) {
      return
    }
    const profile: Profile = { name, ...data }
    const next = { ...config, profiles: upsert(profiles, profile), lastProfile: name }
    setConfig(next)
    await api.saveProfile(profile)
    addLog({ ts: Date.now(), level: 'info', msg: `已保存档案：${name}` })
  }

  const overwriteSave = async () => {
    const data = readJumphost()
    if (!data) return
    const name = config.lastProfile
    if (!name) {
      alert('当前没有选中档案，请用「另存为新档案」')
      return
    }
    const profile: Profile = { name, ...data }
    const next = { ...config, profiles: upsert(profiles, profile) }
    setConfig(next)
    await api.saveProfile(profile)
    addLog({ ts: Date.now(), level: 'info', msg: `已覆盖保存档案：${name}` })
  }

  const deleteProfile = async () => {
    const name = config.lastProfile
    if (!name) return
    if (!window.confirm(`删除档案「${name}」？`)) return
    const next = {
      ...config,
      profiles: profiles.filter((p) => p.name !== name),
      lastProfile: '',
    }
    setConfig(next)
    await api.deleteProfile(name)
    addLog({ ts: Date.now(), level: 'info', msg: `已删除档案：${name}` })
  }

  const testConnection = async () => {
    const data = readJumphost()
    if (!data) return
    setTesting(true)
    addLog({ ts: Date.now(), level: 'info', msg: `测试连接 ${data.host}:${data.port} ...` })
    try {
      await api.testConnection(data)
      addLog({ ts: Date.now(), level: 'info', msg: '连接成功 ✓' })
    } catch (e) {
      addLog({ ts: Date.now(), level: 'error', msg: `连接失败：${String(e)}` })
    } finally {
      setTesting(false)
    }
  }

  return (
    <section className="rounded-lg bg-surface p-3">
      <h2 className="mb-2 text-[15px] font-bold">跳板机配置</h2>

      <div className="mb-2 flex items-center gap-2">
        <select
          className="h-8 w-44 rounded-md border border-border bg-surface-2 px-2 text-[13px] outline-none"
          value={config.lastProfile}
          onChange={(e) => onProfileChange(e.target.value)}
        >
          <option value="">— 选择档案 —</option>
          {profiles.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}
            </option>
          ))}
        </select>
        <span className="text-dim">档案</span>
        <button className="btn" onClick={saveAsNew}>
          另存为新档案
        </button>
        <button className="btn" onClick={overwriteSave}>
          覆盖保存
        </button>
        <button className="btn btn-danger" onClick={deleteProfile}>
          删除档案
        </button>
        <button
          className="btn ml-auto"
          onClick={testConnection}
          disabled={testing}
        >
          {testing ? '测试中…' : '测试连接'}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">
          <span className="text-dim">主机</span>
          <input
            className="input w-40"
            placeholder="如 10.0.0.1"
            value={host}
            onChange={(e) => setHost(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">端口</span>
          <input
            className="input w-14"
            placeholder="22"
            value={port}
            onChange={(e) => setPort(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">用户名</span>
          <input
            className="input w-28"
            placeholder="root"
            value={user}
            onChange={(e) => setUser(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1">
          <span className="text-dim">密码</span>
          <input
            className="input w-32"
            type={pwdVisible ? 'text' : 'password'}
            placeholder="password"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
          />
        </label>
        <button
          className="btn btn-ghost w-8"
          onClick={() => setPwdVisible((v) => !v)}
        >
          {pwdVisible ? '隐' : '显'}
        </button>
      </div>
    </section>
  )
}

function upsert(profiles: Profile[], profile: Profile): Profile[] {
  const idx = profiles.findIndex((p) => p.name === profile.name)
  if (idx >= 0) {
    const next = [...profiles]
    next[idx] = profile
    return next
  }
  return [...profiles, profile]
}
