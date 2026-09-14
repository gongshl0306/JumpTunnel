// 协议推断与连接命令模板（对齐旧版 main.py 的常量表）

export const HTTPS_PORTS = new Set(['443', '8443'])
export const HTTP_PORTS = new Set(['80', '8080', '8000'])

export const TCP_SERVICE_PORTS: Record<string, string> = {
  '22': 'ssh',
  '3306': 'mysql',
  '6379': 'redis',
  '5432': 'postgres',
  '27017': 'mongodb',
  '1433': 'mssql',
  '1521': 'oracle',
  '9092': 'kafka',
  '5672': 'rabbitmq',
  '8500': 'consul',
}

export const SCHEMES = [
  'http',
  'https',
  'tcp',
  'ssh',
  'mysql',
  'redis',
  'postgres',
  'mongodb',
] as const

// 各 tcp 服务对应的本地连接命令模板（{port}/{user} 占位）
// ssh 在 localDisplay 中单独处理（连本地映射端口）
const TCP_COMMAND_TEMPLATES: Record<string, string> = {
  mysql: 'mysql -h localhost -P {port} -u root -p',
  redis: 'redis-cli -h localhost -p {port}',
  postgres: 'psql -h localhost -p {port} -U postgres',
  mongodb: 'mongosh --host localhost --port {port}',
  mssql: 'sqlcmd -S localhost,{port} -U sa -P',
  oracle: 'sqlplus user/pass@localhost:{port}/ORCL',
  kafka: '',
  rabbitmq: '',
  consul: '',
  tcp: '',
}

export function isWebScheme(scheme: string): boolean {
  return scheme === 'http' || scheme === 'https'
}

/** 根据目标端口推断协议 */
export function guessScheme(port: string): string {
  if (!port) return 'http'
  if (HTTPS_PORTS.has(port)) return 'https'
  if (HTTP_PORTS.has(port)) return 'http'
  const svc = TCP_SERVICE_PORTS[port]
  if (svc && (SCHEMES as readonly string[]).includes(svc)) return svc
  return 'tcp'
}

/** 生成本地 URL / 连接命令字符串 */
export function localDisplay(
  scheme: string,
  port: number | null,
  targetUser: string,
): string {
  if (isWebScheme(scheme)) {
    if (!port) return `${scheme}://localhost:（待启动，自动分配端口）`
    if ((scheme === 'http' && port === 80) || (scheme === 'https' && port === 443)) {
      return `${scheme}://localhost`
    }
    return `${scheme}://localhost:${port}`
  }
  // ssh：目标 22 端口已映射到本地端口，直接连本地端口即可，
  // 输入的是目标机器的密码（跳板机认证在建隧道时已自动完成）
  if (scheme === 'ssh') {
    if (!port) return 'localhost:（待启动，自动分配端口）  [ssh]'
    return `ssh -p ${port} ${targetUser || 'root'}@localhost`
  }
  if (!port) return `localhost:（待启动，自动分配端口）  [${scheme}]`
  const tmpl = TCP_COMMAND_TEMPLATES[scheme] ?? 'localhost:{port}'
  if (tmpl === '') return `localhost:${port}  [${scheme}]`
  return tmpl.replace('{port}', String(port)).replace('{user}', targetUser || 'root')
}
