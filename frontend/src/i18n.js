/**
 * 集中式显示层本地化（i18n）。
 *
 * 设计原则：
 *  - 数据层（后端 / API）始终返回稳定的英文枚举标识（如 "diligent"、"M"、
 *    "autonomy_support"），作为跨语言不变的键。
 *  - 所有"面向用户的有意义文本"在显示时经本模块映射为当前语言。
 *  - 术语与符号（Hedges' g、95% CI、p_know、Δ、L-Model、P/R/S 等）按用户要求
 *    保留原文，不做翻译。
 *
 * 扩展多语种：在 locales 中新增一个语言对象（如 en），并把 CURRENT_LOCALE
 * 切换为对应键即可，无需改动任何页面组件。
 */

// 当前界面语言。
export const CURRENT_LOCALE = 'zh'

const zh = {
  // 性别（个体档案）
  gender: {
    M: '男',
    F: '女',
  },

  // 人格标签
  personality: {
    diligent: '勤奋',
    creative: '有创造力',
    social: '善于社交',
    analytical: '善于分析',
    artistic: '有艺术天赋',
  },

  // 兴趣
  interests: {
    math: '数学',
    reading: '阅读',
    sports: '体育',
    music: '音乐',
    coding: '编程',
    art: '艺术',
  },

  // 教师教学风格
  teachingStyle: {
    autonomy_support: '自主支持型',
    directive: '指令型',
    balanced: '平衡型',
    laissez_faire: '放任型',
  },

  // 场景（五场景 + 家庭/碎片）
  scene: {
    school: '学校',
    social: '社交',
    shadow_edu: '课外班',
    self_study: '自学',
    home: '家庭',
    parent: '家庭',
    fragment: '碎片',
  },

  // 事件类型（时间轴 / 生命历程）
  eventType: {
    classroom: '课堂教学',
    peer_interaction: '同伴互动',
    homework: '作业',
    exam: '考试',
    holiday: '假期',
  },

  // 事件描述（生命历程关键事件）
  eventDescription: {
    'Midterm exam': '期中考试',
    'Semester break': '学期假期',
  },

  // 子群切片标签
  subgroupLabel: {
    'High SES': '高社会经济地位',
    'Medium SES': '中社会经济地位',
    'Low SES': '低社会经济地位',
    Male: '男生',
    Female: '女生',
    'High confidence': '高自信',
    'Medium confidence': '中自信',
    'Low confidence': '低自信',
  },

  // 干预类型（场景比较）
  interventionType: {
    cognitive_support: '认知支持',
  },

  // 家长参与方式（FR-F7）
  parentStyle: {
    autonomy_support: '自主支持型',
    directive: '控制型',
    permissive: '放任型',
    uninvolved: '忽视型',
  },

  // 干预候选（成果输出中心：报告 / 研究计划 / 建议）
  intervention: {
    cognitive_support: '认知支持',
    autonomy_teaching: '自主支持型教学',
    parent_involvement: '家长参与提升',
    shadow_edu_reduction: '课外负担削减',
    sleep_schedule: '作息规律化',
  },

  // 失真类别（差距分析 M5）
  distortion: {
    overestimate: '高估',
    underestimate: '低估',
    variance_mismatch: '方差失配',
    shape_mismatch: '形态失配',
    none: '无失真',
  },

  // 差距指标族（差距分析 M5）
  gapMetric: {
    learning_curve: '学习曲线',
    error_dist: '错误分布',
    first_correct: '首次正确潜伏期',
    variance_ratio: '方差比',
  },

  // 运行 / 分支状态
  status: {
    completed: '已完成',
    running: '运行中',
    pending: '等待中',
    failed: '失败',
  },

  // 全方位档案（FR-A1，23 域 210+ 字段）字段名中文映射。
  // 数据层保持英文字段键不变，显示时经此表本地化，避免非技术用户看到英文键名。
  archiveField: {
    // D1 身份与学籍
    name: '姓名', gender: '性别', birth_date: '出生日期', birth_place: '出生地',
    grade: '年级', class_id: '班级', student_status: '学籍状态',
    nationality: '国籍', household_registration: '户籍类型',
    // D2 家庭与成长背景
    family_structure: '家庭结构', ses_level: '社会经济地位', ses_index: '社会经济指数',
    father_occupation: '父亲职业', mother_occupation: '母亲职业',
    father_education: '父亲学历', mother_education: '母亲学历',
    only_child: '是否独生子女', household_income_band: '家庭收入档次',
    // D3 人格与心理特质
    big5_openness: '大五·开放性', big5_conscientiousness: '大五·尽责性',
    big5_extraversion: '大五·外向性', big5_agreeableness: '大五·宜人性',
    big5_neuroticism: '大五·神经质', mbti: 'MBTI 类型',
    personality_tags: '人格标签', temperament: '气质类型',
    // D4 能力与天赋
    logical_mathematical: '逻辑数学智能', verbal_linguistic: '语言智能',
    spatial: '空间智能', musical: '音乐智能', bodily_kinesthetic: '身体动觉智能',
    interpersonal: '人际智能', intrapersonal: '内省智能',
    naturalistic: '自然观察智能', gifted_domain: '特长领域',
    // D5 学业档案
    overall_achievement: '总体成就分', chinese_score: '语文成绩', math_score: '数学成绩',
    english_score: '英语成绩', science_score: '理科成绩',
    class_rank_percentile: '班级排名百分位', academic_trend: '学业趋势',
    main_misconception: '主要迷思概念',
    // D6 身心健康
    physical_fitness_score: '体质健康分', bmi_category: 'BMI 分类',
    vision_status: '视力状况', sleep_quality: '睡眠质量', chronic_fatigue: '慢性疲劳',
    mental_health_index: '心理健康指数', exercise_frequency_weekly: '每周锻炼次数',
    self_rated_health: '自评健康',
    // D7 品德与社会实践
    moral_rating: '品德评定', volunteer_hours_year: '年志愿服务时长',
    political_status: '政治面貌', social_practice_count: '社会实践次数',
    leadership_role: '学生干部职务', rule_compliance: '规则遵守度',
    civic_awareness: '公民意识', community_engagement: '社区参与度',
    // D8 兴趣与生活方式
    interests: '兴趣爱好', hobby_depth: '爱好投入深度', art_literacy: '艺术素养',
    club_participation: '社团参与', screen_leisure_hours_daily: '日均屏幕娱乐时长',
    lifestyle_regularity: '生活规律性',
    // D9 关系与经历
    key_life_event: '关键生活事件', teacher_interaction_style: '师生互动风格',
    classroom_positions_held: '担任过的班级职务', notable_achievement: '突出成就',
    turning_point_event: '转折性事件',
    // D10 家庭深度结构与照护史
    primary_caregiver: '主要照护者', caregiver_warmth: '照护者温暖度',
    caregiver_control: '照护者控制度', family_cohesion: '家庭凝聚力',
    family_conflict_level: '家庭冲突水平', parental_marital_quality: '父母婚姻质量',
    economic_stress: '经济压力', cultural_capital: '文化资本',
    home_learning_environment: '家庭学习环境', siblings_count: '兄弟姐妹数',
    birth_order: '出生顺序', intergenerational_education_gap: '代际教育差距',
    // D11 隐私与敏感信息（虚拟合成数据，完整展示）
    chronic_condition: '慢性疾病', adhd_indicator: '多动倾向指标',
    anxiety_indicator: '焦虑倾向指标', depression_indicator: '抑郁倾向指标',
    absenteeism_days_year: '年缺勤天数', medication_history: '用药史',
    family_income_detail: '家庭收入明细', parent_health_issue: '家长健康问题',
    economic_hardship_flag: '经济困难标记',
    psychological_counseling_history: '心理咨询史', sleep_disorder_flag: '睡眠障碍标记',
    substance_exposure: '物质接触史', self_harm_risk_flag: '自伤风险标记',
    disability_flag: '残疾标记',
    // D12 同伴、亚文化与数字生活
    peer_group_quality: '同伴群体质量', close_friends_count: '密友数量',
    peer_academic_norm: '同伴学业规范', deviant_peer_exposure: '偏差同伴接触',
    subculture_affiliation: '亚文化归属', idol_worship_intensity: '偶像崇拜强度',
    gaming_hours_weekly: '每周游戏时长', short_video_hours_daily: '日均短视频时长',
    social_media_platforms: '社交平台', online_social_activity: '线上社交活跃度',
    cyberbullying_exposure: '网络欺凌接触', device_ownership: '设备拥有情况',
    digital_literacy: '数字素养',
    // D13 隐性心理特质
    intrinsic_motivation: '内在动机', extrinsic_motivation: '外在动机',
    autonomy_need: '自主需要', competence_need: '胜任需要',
    relatedness_need: '关系需要', resilience_adversity_quotient: '抗逆力（逆商）',
    self_drive_index: '自我驱动指数', goal_orientation: '目标导向',
    attribution_style: '归因风格', metacognitive_calibration: '元认知校准',
    self_regulation: '自我调节', growth_mindset: '成长型思维',
    academic_burnout: '学业倦怠',
    // D14 发展阶段与年龄效应
    age: '年龄', pubertal_stage: '青春期阶段', rebelliousness: '叛逆性',
    identity_exploration: '自我同一性探索', school_transition_stress: '升学适应压力',
    autonomy_development: '自主性发展', age_norm_pressure: '年龄规范压力',
    // D15 认知与学习过程画像
    cognitive_style_field: '认知风格（场依存/独立）',
    impulsivity_vs_reflection: '冲动—沉思倾向', strategy_elaboration: '精加工策略',
    strategy_organization: '组织策略', strategy_rehearsal: '复述策略',
    strategy_retrieval_self_testing: '提取练习/自测策略',
    working_memory_capacity: '工作记忆容量', processing_speed: '加工速度',
    error_careless_slip_rate: '粗心失误率', error_misconception_rate: '迷思概念错误率',
    error_knowledge_gap_rate: '知识缺口错误率', transfer_ability: '迁移能力',
    help_seeking_tendency: '求助倾向',
    // D16 学校与课堂情境
    school_tier: '学校层次', class_climate_cohesion: '班级氛围·凝聚力',
    class_climate_competition: '班级氛围·竞争性', class_climate_support: '班级氛围·支持性',
    teacher_support_perceived: '感知教师支持', classroom_autonomy_space: '课堂自主空间',
    peer_competition_intensity: '同伴竞争强度', school_resources_index: '学校资源指数',
    class_size: '班级规模', boarding_status: '走读/住校', commute_minutes: '通勤时长（分钟）',
    // D17 特殊才能与特殊教育需求
    gifted_flag: '资优标记', learning_disability_flag: '学习障碍标记',
    twice_exceptional_flag: '双重特殊标记', sen_category: '特殊教育需求类别',
    accommodation_needed: '所需考试便利', talent_development_track: '特长培养方向',
    enrichment_participation: '拓展课程参与度', individualized_plan_flag: '个别化教育计划标记',
    // D18 课外学习生态
    shadow_edu_hours_weekly: '每周课外班时长', tutoring_subjects: '补习科目',
    tutoring_format: '补习形式', tutoring_quality: '补习质量',
    shadow_edu_cost_yearly: '年课外教育支出', self_study_hours_weekly: '每周自学时长',
    self_study_effectiveness: '自学有效性', online_learning_platforms: '在线学习平台',
    parent_academic_involvement: '家长学业参与度', homework_hours_daily: '日均作业时长',
    academic_overload_flag: '学业超载标记', shadow_edu_dependency: '课外班依赖度',
    weekend_study_load: '周末学习负担',
    // D19 家庭生活与作息
    weekday_wake_time: '工作日起床时间', weekday_sleep_time: '工作日就寝时间',
    sleep_duration_hours: '睡眠时长（小时）', breakfast_regularity: '早餐规律性',
    after_school_structure: '放学后安排结构性',
    family_dinner_frequency_weekly: '每周家庭晚餐次数', weekend_screen_hours: '周末屏幕时长',
    physical_activity_hours_weekly: '每周体育活动时长', part_time_or_chores: '兼职/家务',
    daily_routine_stability: '日常作息稳定性', morningness_eveningness: '晨型—夜型倾向',
    leisure_reading_hours_weekly: '每周休闲阅读时长',
    // D20 家长角色连接点
    primary_parent_id: '主要家长 ID', parent_relation_quality: '亲子关系质量',
    parent_involvement_perceived: '感知家长参与',
    // D21 恋爱与亲密关系
    romance_status: '恋爱状态', romance_intensity: '恋爱强度',
    romance_time_investment_weekly: '每周恋爱时间投入',
    romance_emotional_impact: '恋爱情感影响',
    romance_academic_interference: '恋爱对学业的干扰', parent_awareness: '家长知情程度',
    peer_norm_romance: '同伴恋爱规范', emotional_maturity: '情感成熟度',
    attachment_style: '依恋类型', breakup_history: '分手经历',
    // D22 同伴社会网络
    network_size: '网络规模', network_density: '网络密度',
    centrality_degree: '度中心性', betweenness_centrality: '中介中心性',
    clique_membership: '小团体归属', peer_influence_susceptibility: '同伴影响易感性',
    friendship_stability: '友谊稳定性', cross_gender_friendships: '异性朋友数',
    mentor_relationship: '导师关系', social_support_perceived: '感知社会支持',
    loneliness_index: '孤独指数',
    // D23 成长关键事件与生命历程
    recent_positive_events: '近期积极事件', recent_negative_events: '近期消极事件',
    event_stress_load: '事件压力负荷', turning_point_count: '转折点数量',
    family_change_event: '家庭变动事件', academic_milestone: '学业里程碑',
    health_event: '健康事件', event_recovery_capacity: '事件恢复力',
    life_satisfaction: '生活满意度',
    // 嵌套对象（如 time_allocation）内部键
    school: '学校', homework: '作业', self_study: '自学', recreation: '休闲',
  },
}

// 语言包注册表。新增语言时在此添加，例如：en: { gender: { M: 'Male', ... } }
const locales = { zh }

/**
 * 通用查询：返回 `category` 类目下 `value` 的本地化标签；
 * 若无对应映射（或 value 为空），原样返回，保证不丢信息。
 */
export function t(category, value) {
  if (value === null || value === undefined) return value
  const dict = locales[CURRENT_LOCALE]?.[category]
  if (dict && Object.prototype.hasOwnProperty.call(dict, value)) {
    return dict[value]
  }
  return value
}

/**
 * 姓名本地化：Student_3 -> 学生3，Teacher_5 -> 教师5。
 * 非该模式的姓名原样返回。
 */
export function localName(name) {
  if (typeof name !== 'string') return name
  return name
    .replace(/^Student_(\d+)$/, '学生$1')
    .replace(/^Teacher_(\d+)$/, '教师$1')
}

// 年级数字的中文表达（1-12）。
const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']

/**
 * 年级本地化："Grade 8" -> 八年级。非该模式原样返回。
 */
export function localGrade(grade) {
  const m = /^Grade\s+(\d+)$/.exec(String(grade ?? ''))
  if (!m) return grade
  const n = parseInt(m[1], 10)
  return `${CN_NUM[n] ?? n}年级`
}

/**
 * 将后端返回的常见英文错误信息本地化为中文（提示类内容）。
 * 未识别的信息原样返回，保留技术细节以便排查。
 */
export function localizeApiError(msg) {
  if (typeof msg !== 'string') return msg
  return msg
    .replace(/Run ([A-Za-z0-9_]+) not found/, '运行 $1 不存在（后端重启后需重新创建）')
    .replace(/Student ([A-Za-z0-9_]+) not found/, '学生 $1 不存在')
    .replace(/No trajectory for ([A-Za-z0-9_]+)/, '暂无 $1 的轨迹数据')
}
