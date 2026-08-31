// 日志面板：等宽字体，自动滚动到底部

import { useEffect, useRef } from 'react'
import { useApp } from '../stores'

export function LogPanel() {
  const { logs } = useApp()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  return (
    <section className="rounded-lg bg-surface p-3">
      <h2 className="mb-1 text-[13px] font-bold">日志</h2>
      <div
        ref={ref}
        className="h-24 overflow-y-auto rounded-md bg-bg p-2 font-mono text-[12px] leading-5"
      >
        {logs.length === 0 ? (
          <span className="text-dim">（暂无日志）</span>
        ) : (
          logs.map((l, i) => (
            <div
              key={i}
              className={l.level === 'error' ? 'text-danger' : 'text-text'}
            >
              {new Date(l.ts).toLocaleTimeString()} {l.msg}
            </div>
          ))
        )}
      </div>
    </section>
  )
}
