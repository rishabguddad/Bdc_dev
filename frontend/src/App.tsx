import React from 'react'
import { useEffect, useState } from 'react'
import { Layout, Typography, Select, Button, Space, message, Divider, Card, Row, Col, Tag } from 'antd'
import axios from 'axios'

const { Header, Content, Footer } = Layout
const { Title } = Typography

// Prefer configured base, otherwise default to current host with port 8000
const API_BASE = import.meta.env.VITE_API_BASE
  || `${window.location.protocol}//${window.location.hostname}:${import.meta.env.VITE_API_PORT || '8000'}`

function App() {
  const [states, setStates] = useState<string[]>([])
  const [state, setState] = useState<string>()
  const [counties, setCounties] = useState<string[]>([])
  const [countySelection, setCountySelection] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [attributes, setAttributes] = useState<string[]>([])
  const [selectedAttributes, setSelectedAttributes] = useState<string[]>([])

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

  // load attributes once user has chosen at least one county (as requested)
  useEffect(() => {
    if (!state || countySelection.length === 0) { setAttributes([]); setSelectedAttributes([]); return }
    axios.get(`${API_BASE}/export/attributes`, { params: { state }})
      .then(res => setAttributes(res.data))
      .catch(() => message.error('Failed to load attributes'))
  }, [state, countySelection])

  const exportCsv = async () => {
    if (!state) { message.warning('Select a state'); return }
    if (countySelection.length === 0) { message.warning('Select at least one county'); return }
    if (selectedAttributes.length === 0) { message.warning('Select attributes to export'); return }
    setLoading(true)
    try {
      const body = { state, counties: countySelection, attributes: selectedAttributes }
      const res = await axios.post(`${API_BASE}/export/csv`, body, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // Try to extract filename from header, fallback
      const cd = res.headers['content-disposition'] as string | undefined
      let filename = 'export.csv'
      if (cd) {
        const m = /filename="?([^";]+)"?/i.exec(cd)
        if (m && m[1]) filename = m[1]
      }
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      try {
        const blob: Blob | undefined = err?.response?.data
        if (blob && (blob as any).text) {
          const text = await (blob as any).text()
          try {
            const json = JSON.parse(text)
            message.error(json.detail || 'Failed to export CSV')
          } catch {
            message.error(text || 'Failed to export CSV')
          }
        } else {
          message.error(err?.message || 'Failed to export CSV')
        }
      } catch {
        message.error('Failed to export CSV')
      }
    } finally { setLoading(false) }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', borderBottom: '1px solid #eee' }}>
        <Title level={3} style={{ margin: 0 }}>BDC CSV Export</Title>
      </Header>
      <Content style={{ padding: 24 }}>
        <Card bordered style={{ maxWidth: 1100, margin: '0 auto' }} bodyStyle={{ paddingBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <div style={{ marginBottom: 8 }}>State</div>
              <Select
                showSearch
                style={{ width: '100%' }}
                placeholder="Select state"
                options={states.map(s => ({ label: s, value: s }))}
                value={state}
                onChange={setState}
                filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
              />
            </Col>
            <Col xs={24} md={8}>
              <div style={{ marginBottom: 8 }}>Counties</div>
              <Select
                mode="multiple"
                allowClear
                disabled={!state}
                style={{ width: '100%' }}
                placeholder="Select counties"
                options={counties.map(c => ({ label: c, value: c }))}
                value={countySelection}
                onChange={setCountySelection}
              />
            </Col>
            <Col xs={24} md={8}>
              <div style={{ marginBottom: 8 }}>Attributes</div>
              <Select
                mode="multiple"
                allowClear
                style={{ width: '100%' }}
                placeholder={state && countySelection.length > 0 ? 'Select attributes to export' : 'Select state and counties to load attributes'}
                options={attributes.map(a => ({ label: a, value: a }))}
                value={selectedAttributes}
                onChange={setSelectedAttributes}
                disabled={attributes.length === 0}
              />
            </Col>
          </Row>
          <Divider style={{ margin: '16px 0' }} />
          <Space wrap>
            {state && <Tag color="blue">State: {state}</Tag>}
            {countySelection.length > 0 && <Tag color="geekblue">Counties: {countySelection.length}</Tag>}
            {selectedAttributes.length > 0 && <Tag color="green">Attributes: {selectedAttributes.length}</Tag>}
          </Space>
        </Card>
        <div style={{ position: 'sticky', bottom: 0, background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(2px)', padding: '12px 0', marginTop: 16 }}>
          <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="primary" size="large" onClick={exportCsv} loading={loading} disabled={attributes.length === 0}>
              Export CSV
            </Button>
          </div>
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>BDC © {new Date().getFullYear()}</Footer>
    </Layout>
  )
}

export default App
