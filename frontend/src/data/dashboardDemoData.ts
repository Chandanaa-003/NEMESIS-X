export interface DemoStatItem {
  id: string
  label: string
  value: string
  helper: string
  badge: string
  accent: 'blue' | 'violet' | 'emerald' | 'amber'
  iconKey: 'videos' | 'events' | 'evidence' | 'sessions'
}

export interface DemoAnalysisItem {
  id: string
  videoName: string
  cameraLabel: string
  status: 'Completed' | 'Sample Queued' | 'Needs Review'
  duration: string
  date: string
  eventsCount: number
  thumbnailTheme: 'blue' | 'violet' | 'slate' | 'indigo'
}

export interface DemoEventItem {
  id: string
  title: string
  timestamp: string
  category: string
  severity: 'High' | 'Medium' | 'Low'
  confidence: string
  sourceVideo: string
}

export interface DemoQuickActionItem {
  id: string
  title: string
  description: string
  to: string
  accent: 'blue' | 'violet'
  iconKey: 'upload' | 'live' | 'evidence' | 'timeline'
}

export interface DemoNotificationItem {
  id: string
  title: string
  time: string
  detail: string
}

export const DEMO_DASHBOARD_STATS: DemoStatItem[] = [
  {
    id: 'stat-videos',
    label: 'Videos Analyzed',
    value: '24',
    helper: 'Sample workspace total',
    badge: 'Demo Data',
    accent: 'blue',
    iconKey: 'videos',
  },
  {
    id: 'stat-events',
    label: 'Events Discovered',
    value: '68',
    helper: 'Illustrative detections',
    badge: 'Demo Data',
    accent: 'violet',
    iconKey: 'events',
  },
  {
    id: 'stat-evidence',
    label: 'Evidence Captured',
    value: '41',
    helper: 'Sample annotated clips',
    badge: 'Demo Data',
    accent: 'emerald',
    iconKey: 'evidence',
  },
  {
    id: 'stat-sessions',
    label: 'Active Monitoring Sessions',
    value: '03',
    helper: 'Simulated streams',
    badge: 'Demo Data',
    accent: 'amber',
    iconKey: 'sessions',
  },
]

export const DEMO_RECENT_ANALYSES: DemoAnalysisItem[] = [
  {
    id: 'an-1',
    videoName: 'north_gate_entry_cam02.mp4',
    cameraLabel: 'CAM-02 · North Gate',
    status: 'Completed',
    duration: '06:14',
    date: 'Nov 25, 2026',
    eventsCount: 4,
    thumbnailTheme: 'blue',
  },
  {
    id: 'an-2',
    videoName: 'loading_bay_shift_b.mp4',
    cameraLabel: 'CAM-05 · Loading Bay',
    status: 'Needs Review',
    duration: '12:48',
    date: 'Nov 25, 2026',
    eventsCount: 7,
    thumbnailTheme: 'violet',
  },
  {
    id: 'an-3',
    videoName: 'perimeter_west_dusk.mp4',
    cameraLabel: 'CAM-08 · West Perimeter',
    status: 'Completed',
    duration: '09:05',
    date: 'Nov 24, 2026',
    eventsCount: 2,
    thumbnailTheme: 'indigo',
  },
  {
    id: 'an-4',
    videoName: 'lobby_concourse_01.mp4',
    cameraLabel: 'CAM-01 · Main Lobby',
    status: 'Sample Queued',
    duration: '04:32',
    date: 'Nov 24, 2026',
    eventsCount: 0,
    thumbnailTheme: 'slate',
  },
]

export const DEMO_RECENT_EVENTS: DemoEventItem[] = [
  {
    id: 'ev-1',
    title: 'Unattended Package Near Egress Lane',
    timestamp: '00:04:18',
    category: 'Object Anomaly',
    severity: 'High',
    confidence: '96%',
    sourceVideo: 'north_gate_entry_cam02.mp4',
  },
  {
    id: 'ev-2',
    title: 'Extended Dwell Time in Restricted Zone B',
    timestamp: '00:02:45',
    category: 'Temporal Loitering',
    severity: 'Medium',
    confidence: '91%',
    sourceVideo: 'loading_bay_shift_b.mp4',
  },
  {
    id: 'ev-3',
    title: 'After-Hours Vehicle Approach Detected',
    timestamp: '00:07:12',
    category: 'Perimeter Motion',
    severity: 'Medium',
    confidence: '94%',
    sourceVideo: 'perimeter_west_dusk.mp4',
  },
  {
    id: 'ev-4',
    title: 'Routine Badge Access Sequence Verified',
    timestamp: '00:01:12',
    category: 'Access Flow',
    severity: 'Low',
    confidence: '98%',
    sourceVideo: 'north_gate_entry_cam02.mp4',
  },
]

export const DEMO_QUICK_ACTIONS: DemoQuickActionItem[] = [
  {
    id: 'qa-upload',
    title: 'Analyze Recorded Video',
    description: 'Upload MP4 or surveillance clips for multi-stage intelligence.',
    to: '/dashboard/new-analysis',
    accent: 'blue',
    iconKey: 'upload',
  },
  {
    id: 'qa-live',
    title: 'Start Live Monitoring',
    description: 'Open real-time stream workspace and bilingual alert rules.',
    to: '/dashboard/live',
    accent: 'violet',
    iconKey: 'live',
  },
  {
    id: 'qa-evidence',
    title: 'Review Evidence',
    description: 'Inspect timestamped keyframes and annotated anomaly clips.',
    to: '/dashboard/evidence',
    accent: 'blue',
    iconKey: 'evidence',
  },
  {
    id: 'qa-timeline',
    title: 'View Event Timeline',
    description: 'Explore chronological events across analyzed video sessions.',
    to: '/dashboard/timeline',
    accent: 'violet',
    iconKey: 'timeline',
  },
]

export const DEMO_NOTIFICATIONS: DemoNotificationItem[] = [
  {
    id: 'notif-1',
    title: 'Sample Event Preview Ready',
    time: '2m ago',
    detail: 'Illustrative alert entry added for north_gate_entry_cam02.mp4.',
  },
  {
    id: 'notif-2',
    title: 'Workspace UI Mode',
    time: 'Today',
    detail: 'Dashboard currently displays demo data until backend APIs connect.',
  },
]
