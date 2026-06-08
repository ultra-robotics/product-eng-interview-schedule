import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './Layout'
import ScheduleEditor from './schedule/ScheduleEditor'
import ScheduleHome from './schedule/ScheduleHome'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/schedule" replace />} />
          <Route path="/schedule" element={<ScheduleHome />} />
          <Route path="/schedule/shift/:shift/:day" element={<ScheduleEditor />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
