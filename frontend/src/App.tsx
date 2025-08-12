import React from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Layout, Typography, Select, Button, Space, Table, message, Tag } from 'antd'
import axios from 'axios'

const { Header, Content, Footer } = Layout
const { Title } = Typography

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function App() {
  const [states, setStates] = useState<string[]>([])
  const [state, setState] = useState<string>()
  const [counties, setCounties] = useState<string[]>([])
  const [countySelection, setCountySelection] = useState<string[]>([])
  const [report, setReport] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<{columns: string[]; rows: any[][]}>({columns: [], rows: []})

  // load states
  useEffect(() => {
    axios.get(`${API_BASE}/meta/states`).then(res => setStates(res.data)).catch(() => message.error('Failed to load states'))
  }, [])

  // load counties when state changes
  useEffect(() => {
    if (!state) { setCounties([]); setCountySelection([]); return }
    axios.get(`${API_BASE}/meta/counties`, { params: { state }})
      .then(res => setCounties(res.data))
      .catch(() => message.error('Failed to load counties'))
  }, [state])

  const reportOptions = useMemo(() => [
    'Location Level',
    'Block Level',
  ], [])

  const fetchReport = async () => {
    if (!state || !report) { message.warning('Select state and report level'); return }
    setLoading(true)
    try {
      const params: any = { script: report, state }
      countySelection.forEach(c => {
        if (!params.counties) params.counties = []
        params.counties.push(c)
      })
      const res = await axios.get(`${API_BASE}/reports/run`, { params })
      setData(res.data)
    } catch (e) {
      message.error('Failed to fetch report')
    } finally { setLoading(false) }
  }

  const columns = data.columns.map((c, idx) => ({ title: c, dataIndex: idx, key: `${idx}` }))
  const datasource = data.rows.map((r, i) => ({ key: i, ...Object.fromEntries(r.map((v, idx) => [idx, v])) }))

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', borderBottom: '1px solid #eee' }}>
        <Title level={3} style={{ margin: 0 }}>BDC Reports</Title>
      </Header>
      <Content style={{ padding: 24 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Space wrap>
            <div>
              <div>State</div>
              <Select
                showSearch
                style={{ width: 240 }}
                placeholder="Select state"
                options={states.map(s => ({ label: s, value: s }))}
                value={state}
                onChange={setState}
                filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
              />
            </div>
            <div>
              <div>Counties</div>
              <Select
                mode="multiple"
                allowClear
                disabled={!state}
                style={{ width: 360 }}
                placeholder="Select counties"
                options={counties.map(c => ({ label: c, value: c }))}
                value={countySelection}
                onChange={setCountySelection}
              />
            </div>
            <div>
              <div>Report level</div>
              <Select
                style={{ width: 240 }}
                placeholder="Select report"
                options={reportOptions.map(r => ({ label: r, value: r }))}
                value={report}
                onChange={setReport}
              />
            </div>
            <div style={{ alignSelf: 'end' }}>
              <Button type="primary" onClick={fetchReport} loading={loading}>Fetch</Button>
            </div>
          </Space>
          {report && (
            <div>
              Selected report: <Tag color="blue">{report}</Tag>
            </div>
          )}
          <Table loading={loading} columns={columns} dataSource={datasource} scroll={{ x: true }} />
        </Space>
      </Content>
      <Footer style={{ textAlign: 'center' }}>BDC © {new Date().getFullYear()}</Footer>
    </Layout>
  )
}

export default App
