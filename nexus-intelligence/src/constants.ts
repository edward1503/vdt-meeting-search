import { Meeting, Participant } from './types';

export const MOCK_PARTICIPANTS: Participant[] = [
  {
    id: '1',
    name: 'Anh Sinh',
    avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuArLx4NOV2sijyoJsFTrNeTZjuiutolid8MCn_8NiOXBHHAk2alzLfdvw0HWohLswFfWMVJJFFfR31DVEJwNGFTmY8m3m9Yv6N5dukx0dbSbhjba8cKlyK0XkFz_Wdp7Mv-Y7Q5_m7alzCVLVI5Tq0gO5srD2oHhEckLSuptPIi3MFmVBZhCB61MAfq8BOt2LCHTESclZerPcBJ5b8VfT45oy1mni-tcwzxH8eBrZ8kzf92JzlfpWZZ95kZKg9xjZh-zBGNStun8w',
    role: 'Chair',
    unit: 'VTS'
  },
  {
    id: '2',
    name: 'Chị Lan',
    avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC-M-ditt59a0HZMmQIuG0AH-2gkl-EKCPPDYg2rVhNITEGogiIYZKLJQguzK_xoAifh16ZXl1nf7DiENcn_67Z_E5g4TPbYEM8bQ_YFc05TpUPmGI4yygCAvCusVkNwde4H4e9pAJBySOg_Xd-Ze-DgyLuRNoeQNeCSiDDLulFKtMd5uMPqMIhM1UQ5yCQJXFhknbqAwnkBXXM5dMtnEQSDPqZmz8MzPnDV0k6IkfvAmTpcmFDaVHQiBJFQ3NIv3x0EnptBrEkPA',
    unit: 'VTS'
  },
  {
    id: '3',
    name: 'Anh Bình',
    avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBqAno_1mQuXa2S-ZvQlf3dlvHi6HI8jzMkW86ZQKdzEQYhZGUJrRPycqlW7Ww8DS4rO2wuDjF4mz9F4724-5Q2cgm2kX94L79EhhdjBucA4J81TgDwe_PkMmA2F2Vom4-RAfnNRFkYIA9i3OOHBGle1SrJjoOgJnrbH0HvSQrMO8q0ixCg848rC9pOpu1NVYod2ER6EJPjKtfw0ZcFFY5sD6ZYFmL-rycKFvQ8KMI27otE6BVT6ToIq6PVygIiYtGn3_oMSAFP1Q',
    unit: 'VTS'
  },
  {
    id: '4',
    name: 'Thư ký',
    avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuB1IUZN7PgRXpEtwTzc6GES13uo1zG5DUzG6f0l1FGclXYbItaw6xkVCl1ApGi4WM76JvSy-qcr4_ytYhiqKzqEv1gs26q-EL1Pgl8uUf2gfvLDy6wU4KcJ-hL8iMhZIbPCt63F3pmnEqNiX_hSz2ZuZ_0hKXwEpgAsSzBM1wtkU39SZiWLivQWD37sK5koiDpyfO2W8w_1Rer-iNn3KZ_YIoMf0ItURCgWPiISkqEHQQlBojEZhc_Wc155ASIIdQ74T6rpT8iApA',
    unit: 'Strategy'
  }
];

export const MOCK_MEETINGS: Meeting[] = [
  {
    id: 'MEET-1025',
    title: 'Q3 Strategic Planning: VTS Digital Transformation',
    date: '24 Oct, 2023',
    time: '09:30 AM',
    duration: '150 mins',
    location: 'Phòng họp 602, Tòa nhà Trụ sở',
    participants: MOCK_PARTICIPANTS,
    relevance: 95,
    source: 'AMI Corpus',
    keywords: ['Nghị định 105', 'Chuyển đổi số', 'Kế hoạch Q3', 'Bảo mật', 'VTS'],
    snippet: '...Trong phiên thảo luận về khung pháp lý mới, anh Sinh đã nhấn mạnh tầm quan trọng của việc rà soát lại các quy trình vận hành nội bộ để đảm bảo tuân thủ tuyệt đối Nghị định 105. Ông đề xuất thành lập tổ phản ứng nhanh để xử lý các vướng mắc phát sinh ngay trong giai đoạn chuyển đổi...'
  },
  {
    id: 'MEET-1026',
    title: 'Decree 105 Compliance Audit - Session A',
    date: '23 Oct, 2023',
    time: '02:00 PM',
    duration: '60 mins',
    location: 'Meeting Room 401',
    participants: [MOCK_PARTICIPANTS[0], MOCK_PARTICIPANTS[1]],
    relevance: 72,
    source: 'AMI Corpus',
    keywords: ['Audit', 'Compliance', 'Decree 105'],
    snippet: '...Về phía đại diện Ban, Nguyễn Quốc Sinh đưa ra các con số cụ thể về tác động của Nghị định 105 đối với hệ thống quản lý dữ liệu hiện hành...'
  },
  {
    id: 'MEET-1027',
    title: 'Network Optimization Project Sync',
    date: '22 Oct, 2023',
    time: '11:15 AM',
    duration: '45 mins',
    location: 'Virtual',
    participants: MOCK_PARTICIPANTS.slice(0, 3),
    relevance: 88,
    source: 'QMSum',
    keywords: ['Network', 'Optimization', 'Sync'],
    snippet: '...Nội dung tập trung vào việc tối ưu hóa băng thông cho các trạm 5G mới triển khai tại khu vực phía Bắc...'
  },
  {
    id: 'MEET-1028',
    title: 'Weekly Leadership Review - Q4 Forecast',
    date: '21 Oct, 2023',
    time: '08:00 AM',
    duration: '90 mins',
    location: 'Board Room',
    participants: [MOCK_PARTICIPANTS[0]],
    relevance: 45,
    source: 'Strategy',
    keywords: ['Leadership', 'Q4', 'Forecast'],
    snippet: '...Báo cáo tài chính sơ bộ cho tháng 10 cho thấy sự tăng trưởng vượt bậc trong lĩnh vực chuyển đổi số...'
  },
  {
    id: 'MEET-1029',
    title: 'Cloud Infrastructure Migration Roadmap',
    date: '20 Oct, 2023',
    time: '04:30 PM',
    duration: '120 mins',
    location: 'Cloud Lab',
    participants: [MOCK_PARTICIPANTS[2]],
    relevance: 61,
    source: 'Technology',
    keywords: ['Cloud', 'Migration', 'Infrastructure'],
    snippet: '...Lộ trình dịch chuyển các hệ thống lõi lên hạ tầng Hybrid Cloud được thảo luận chi tiết...'
  }
];
