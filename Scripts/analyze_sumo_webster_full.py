import sumolib
import pandas as pd
import sys
import os
from collections import defaultdict

# ==================== 【用户配置区】请仔细修改 ====================
# 1. 输入文件
E1_OUTPUT_FILE = "/Users/AkaiSora/Desktop/Kyoto_INT/KyotoU_ICP/III_second/Transportation Management/Hyakumanben Exe/Revised/Original_Non-peak/e1output.xml"   # E1检测器输出文件
E2_OUTPUT_FILE = "/Users/AkaiSora/Desktop/Kyoto_INT/KyotoU_ICP/III_second/Transportation Management/Hyakumanben Exe/Revised/Original_Non-peak/e2output.xml"   # E2检测器输出文件

# 2. 全局信号参数
SIGNAL_CYCLE = 130.0  # 信号总周期(秒) = 45+10+7+3+45+10+7+3

# 3. 各流向有效绿灯时间映射（秒）
# 注意：字典的键应该匹配清洗后的检测器ID前缀（如"N_Thru_", "N_Left_"）
# 直行 = 阶段0(45s) + 阶段1(10s) = 55s
# 转向 = 阶段0(45s) + 阶段1(10s) + 阶段2(7s) = 62s
GREEN_TIME_BY_DETECTOR_PREFIX = {
    # 北进口
    "N_Thru_": 55.0,   # 北直行
    "N_Left_": 62.0,   # 北左转
    "N_Right_": 62.0,  # 北右转
    # 南进口
    "S_Thru_": 55.0,
    "S_Left_": 62.0,
    "S_Right_": 62.0,
    # 东进口
    "E_Thru_": 55.0,
    "E_Left_": 62.0,
    "E_Right_": 62.0,
    # 西进口
    "W_Thru_": 55.0,
    "W_Left_": 62.0,
    "W_Right_": 62.0,
}
DEFAULT_GREEN_TIME = 55.0  # 默认值（用于未匹配的检测器）

# 4. 饱和流率配置（辆/小时） - 单车道的基准值
BASE_SATURATION_FLOW = {
    "Thru": 1500.0,   # 单车道的直行饱和流率
    "Left": 1500.0,   # 单车道的左转饱和流率
    "Right": 1500.0,  # 单车道的右转饱和流率
}

# 5. 各进口方向直行车道数量（请根据实际路网修改！）
THROUGH_LANE_COUNT = {
    "N": 2,  # 北进口直行车道数
    "S": 2,  # 南进口直行车道数
    "E": 2,  # 东进口直行车道数
    "W": 2,  # 西进口直行车道数
}

# 6. 输出文件
DETAILED_OUTPUT_CSV = "detector_analysis_detailed.csv"   # 车道级详细结果
AGGREGATED_OUTPUT_CSV = "detector_analysis_aggregated.csv" # 流向级聚合结果

# ==================== 核心函数定义 ====================

def clean_detector_id(raw_id):
    """
    清洗检测器ID，移除_E1/_E2后缀
    例如：将"N_Left_1_E1"转换为"N_Left_1"
    """
    if raw_id.endswith('_E1') or raw_id.endswith('_E2'):
        return raw_id[:-3]  # 去掉最后三个字符
    return raw_id

def parse_detector_id(det_id):
    """
    从清洗后的检测器ID解析方向和流向
    返回: (direction, flow_type, lane_num)
    例如: "N_Thru_1" -> ("N", "Thru", 1)
    """
    parts = det_id.split('_')
    if len(parts) >= 3:
        direction = parts[0]  # N, S, E, W
        flow_type = parts[1]  # Thru, Left, Right
        try:
            lane_num = int(parts[2])  # 车道序号
        except ValueError:
            lane_num = 1
        return direction, flow_type, lane_num
    elif len(parts) == 2:
        return parts[0], parts[1], 1
    else:
        return "Unknown", "Thru", 1

def main():
    print("=" * 60)
    print("SUMO交叉口性能分析脚本 (Webster模型 v2.0)")
    print("=" * 60)
    print(f"理论参数: 周期C={SIGNAL_CYCLE}s, 直行绿灯55s, 转向绿灯62s")
    print(f"饱和流率: 直行{BASE_SATURATION_FLOW['Thru']}, 左转{BASE_SATURATION_FLOW['Left']}, 右转{BASE_SATURATION_FLOW['Right']} veh/h")
    
    # 检查输入文件
    for file_path in [E1_OUTPUT_FILE, E2_OUTPUT_FILE]:
        if not os.path.exists(file_path):
            print(f"错误: 找不到输入文件 {file_path}")
            sys.exit(1)
    
    # 1. 解析E1数据
    print(f"\n1. 正在解析E1文件: {E1_OUTPUT_FILE}")
    e1_data = parse_e1_data(E1_OUTPUT_FILE)
    if not e1_data:
        print("错误: 未能从E1文件中解析出任何数据。")
        sys.exit(1)
    print(f"   已读取 {len(e1_data)} 条E1记录")
        
    # 2. 解析E2数据
    print(f"\n2. 正在解析E2文件: {E2_OUTPUT_FILE}")
    e2_data = parse_e2_data(E2_OUTPUT_FILE)
    if not e2_data:
        print("警告: 未能从E2文件中解析出数据，排队和延误数据可能为空。")
    else:
        print(f"   已读取 {len(e2_data)} 条E2记录")
    
    # 3. 计算所有车道级指标
    print("\n3. 正在计算车道级指标 (Webster模型)...")
    lane_level_results = calculate_lane_level_metrics(e1_data, e2_data)
    
    if not lane_level_results:
        print("错误: 未能计算任何结果。")
        sys.exit(1)
        
    # 4. 保存车道级详细结果
    print(f"\n4. 正在保存车道级详细结果: {DETAILED_OUTPUT_CSV}")
    df_detailed = pd.DataFrame(lane_level_results)
    
    # 定义详细结果的列顺序
    detailed_columns = [
        'detector_id_raw', 'detector_id', 'approach', 'flow_type', 'lane_number',
        'interval_begin', 'interval_length_sec',
        'arrival_rate_alpha_veh_per_h', 'saturation_flow_beta_s_veh_per_h',
        'capacity_beta_veh_per_h', 'degree_of_saturation_rho',
        'rho_saturated_rho_s', 'cycle_length_c_sec', 'effective_green_g_sec',
        'effective_red_r_sec', 'expected_queue_q_veh_steady',
        'observed_max_queue_m', 'jamLength_veh', 'uniform_delay_w_u_sec',
        'random_delay_w_r_sec', 'total_delay_webster_sec',
        'observed_avg_delay_sec', 'nVehEntered', 'flow_veh_per_h',
        'occupancy_percent', 'speed_kmh', 'totalTimeLoss_sec'
    ]
    
    existing_cols = [col for col in detailed_columns if col in df_detailed.columns]
    df_detailed = df_detailed[existing_cols]
    df_detailed.to_csv(DETAILED_OUTPUT_CSV, index=False, encoding='utf-8-sig')
    
    # 5. 生成并保存流向级聚合结果
    print(f"\n5. 正在生成流向级聚合结果: {AGGREGATED_OUTPUT_CSV}")
    df_aggregated = create_aggregated_report(df_detailed)
    df_aggregated.to_csv(AGGREGATED_OUTPUT_CSV, index=False, encoding='utf-8-sig')
    
    # 6. 打印摘要
    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)
    print(f"• 车道级详细结果: {DETAILED_OUTPUT_CSV}")
    print(f"• 流向级聚合结果: {AGGREGATED_OUTPUT_CSV}")
    
    unique_detectors = df_detailed['detector_id'].nunique()
    print(f"• 共分析 {unique_detectors} 个检测器（清洗后ID）")
    
    # 检测器ID匹配情况统计
    matched = df_detailed[df_detailed['effective_green_g_sec'] != DEFAULT_GREEN_TIME].shape[0]
    total = df_detailed.shape[0]
    print(f"• 检测器ID匹配率: {matched}/{total} ({matched/total*100:.1f}%)")
    
    # 预览
    print("\n关键指标预览 (前3条记录):")
    preview_cols = ['detector_id', 'flow_type', 'arrival_rate_alpha_veh_per_h', 
                    'degree_of_saturation_rho', 'effective_green_g_sec',
                    'total_delay_webster_sec']
    print(df_detailed[preview_cols].head(3).to_string(index=False))

def parse_e1_data(e1_file):
    """解析E1文件"""
    records = []
    try:
        for interval in sumolib.output.parse(e1_file, 'interval'):
            record = {
                'detector_id_raw': interval.id,  # 原始ID
                'detector_id': clean_detector_id(interval.id),  # 清洗后ID
                'interval_begin': safe_float(interval.begin),
                'interval_end': safe_float(interval.end),
                'nVehEntered': safe_float(interval.nVehEntered),
                'flow': safe_float(interval.flow),
                'occupancy': safe_float(interval.occupancy),
                'speed': safe_float(interval.speed),
            }
            records.append(record)
    except Exception as e:
        print(f"  E1解析错误: {e}")
    return records

def parse_e2_data(e2_file):
    """解析E2文件"""
    records = []
    try:
        for interval in sumolib.output.parse(e2_file, 'interval'):
            record = {
                'detector_id_raw': interval.id,  # 原始ID
                'detector_id': clean_detector_id(interval.id),  # 清洗后ID
                'interval_begin': safe_float(interval.begin),
                'interval_end': safe_float(interval.end),
                'maxJamLengthInMeters': safe_float(interval.maxJamLengthInMeters),
                'jamLength': safe_float(interval.jamLength),
                'timeLoss': safe_float(interval.timeLoss),
                'nVehEntered': safe_float(interval.nVehEntered),
                'nVehSeen': safe_float(interval.nVehSeen),
            }
            records.append(record)
    except Exception as e:
        print(f"  E2解析错误: {e}")
    return records

def calculate_lane_level_metrics(e1_data, e2_data):
    """计算车道级指标 (严格Webster模型)"""
    results = []
    
    # 组织数据
    e1_by_key = {(r['detector_id'], r['interval_begin']): r for r in e1_data}
    e2_by_key = {(r['detector_id'], r['interval_begin']): r for r in e2_data}
    all_keys = set(list(e1_by_key.keys()) + list(e2_by_key.keys()))
    
    if not all_keys:
        return results
    
    print(f"   正在处理 {len(all_keys)} 条数据记录...")
    
    for det_id, interval_begin in sorted(all_keys):
        e1_record = e1_by_key.get((det_id, interval_begin), {})
        e2_record = e2_by_key.get((det_id, interval_begin), {})

        # 从清洗后的ID解析信息
        direction, flow_type, lane_num = parse_detector_id(det_id)
        
        # 基础数据
        if e1_record:
            interval_length = e1_record.get('interval_end', interval_begin + 300) - interval_begin
            nVehEntered = e1_record.get('nVehEntered', 0)
        else:
            interval_length = 300.0
            nVehEntered = e2_record.get('nVehEntered', 0)
        
        nVehSeen = e2_record.get('nVehSeen', e2_record.get('nVehEntered', max(nVehEntered, 1)))

        # === 1. 到达率 (α) ===
        if interval_length > 0:
            alpha_veh_per_h = nVehEntered / (interval_length / 3600.0)
            alpha_veh_per_sec = alpha_veh_per_h / 3600.0
        else:
            alpha_veh_per_h = alpha_veh_per_sec = 0

        # === 2. 获取动态参数 ===
        c = SIGNAL_CYCLE
        
        # 绿灯时间 - 基于清洗后的ID进行匹配
        g = DEFAULT_GREEN_TIME
        for prefix, gt in GREEN_TIME_BY_DETECTOR_PREFIX.items():
            if det_id.startswith(prefix):
                g = gt
                break
        
        r = c - g
        
        # 饱和流率 (β_s)
        base_flow = BASE_SATURATION_FLOW.get(flow_type, 1500.0)
        if flow_type == "Thru":
            lane_count = THROUGH_LANE_COUNT.get(direction, 1)
            beta_s = base_flow * lane_count
        else:
            beta_s = base_flow

        # === 3. 饱和度计算 ===
        # 通行能力 β = β_s * (g/c)
        if c > 0:
            beta_capacity = beta_s * (g / c)
        else:
            beta_capacity = 0
        
        # 常规饱和度 ρ = α / β
        if beta_capacity > 0:
            rho = alpha_veh_per_h / beta_capacity
        else:
            rho = float('inf') if alpha_veh_per_h > 0 else 0
        
        # 饱和期间的 ρ^s = α / β_s
        if beta_s > 0:
            rho_s = alpha_veh_per_h / beta_s
        else:
            rho_s = float('inf') if alpha_veh_per_h > 0 else 0

        # === 4. 排队长度 ===
        if 0 <= rho < 1:
            expected_queue = rho / (1 - rho)
        elif rho >= 1:
            expected_queue = float('inf')
        else:
            expected_queue = 0
            
        observed_max_queue_m = e2_record.get('maxJamLengthInMeters', 0)
        jam_length_veh = e2_record.get('jamLength', 0)

        # === 5. Webster延误计算 ===
        # 均匀延误 w_u = 0.5 * r² / [c * (1-ρ)]
        if rho < 1 and c > 0 and (1 - rho) > 0:
            uniform_delay = (0.5 * r * r) / (c * (1 - rho))
        else:
            uniform_delay = float('inf')

        # 随机延误 w_r = (ρ^s)² / [2α(1-ρ^s)] (α单位: 辆/秒)
        if rho_s < 1 and alpha_veh_per_sec > 0 and (1 - rho_s) > 0:
            random_delay = (rho_s ** 2) / (2 * alpha_veh_per_sec * (1 - rho_s))
        else:
            random_delay = float('inf')

        # Webster总延误 w = 0.9 * (w_u + w_r)
        if uniform_delay != float('inf') and random_delay != float('inf'):
            total_delay_webster = 0.9 * (uniform_delay + random_delay)
        else:
            total_delay_webster = float('inf')

        # === 6. 观测延误 ===
        total_time_loss = e2_record.get('timeLoss', 0)
        observed_avg_delay = total_time_loss / nVehSeen if nVehSeen > 0 else 0

        # === 7. 构建记录 ===
        result = {
            # 标识信息
            'detector_id_raw': e1_record.get('detector_id_raw') or e2_record.get('detector_id_raw', ''),
            'detector_id': det_id,
            'approach': direction,
            'flow_type': flow_type,
            'lane_number': lane_num,
            
            # 时间信息
            'interval_begin': interval_begin,
            'interval_length_sec': round(interval_length, 1),
            
            # 核心参数
            'arrival_rate_alpha_veh_per_h': round(alpha_veh_per_h, 2),
            'saturation_flow_beta_s_veh_per_h': round(beta_s, 2),
            'capacity_beta_veh_per_h': round(beta_capacity, 2),
            'degree_of_saturation_rho': format_value(rho),
            'rho_saturated_rho_s': format_value(rho_s),
            'cycle_length_c_sec': round(c, 1),
            'effective_green_g_sec': round(g, 1),
            'effective_red_r_sec': round(r, 1),
            
            # 排队
            'expected_queue_q_veh_steady': format_value(expected_queue),
            'observed_max_queue_m': round(observed_max_queue_m, 2),
            'jamLength_veh': round(jam_length_veh, 1),
            
            # Webster延误
            'uniform_delay_w_u_sec': format_value(uniform_delay),
            'random_delay_w_r_sec': format_value(random_delay),
            'total_delay_webster_sec': format_value(total_delay_webster),
            
            # 观测值
            'observed_avg_delay_sec': round(observed_avg_delay, 2),
            
            # 原始数据
            'nVehEntered': nVehEntered,
            'flow_veh_per_h': e1_record.get('flow', 0),
            'occupancy_percent': e1_record.get('occupancy', 0),
            'speed_kmh': e1_record.get('speed', 0),
            'totalTimeLoss_sec': total_time_loss,
        }
        results.append(result)
    
    return results

def create_aggregated_report(df_detailed):
    if df_detailed.empty:
        return pd.DataFrame()

    # 创建聚合键: 方向+流向 (如 N_Thru)
    df_detailed['approach_flow'] = df_detailed['approach'] + '_' + df_detailed['flow_type']
    
    # --- 关键修复：在聚合前，将需要计算均值的列中的 ‘INF‘ 替换为 numpy.nan ---
    # 这些列在聚合规则中使用了 ‘mean‘
    mean_columns_to_clean = [
        'degree_of_saturation_rho',
        'rho_saturated_rho_s',
        'uniform_delay_w_u_sec',
        'random_delay_w_r_sec',
        'total_delay_webster_sec',
        'observed_avg_delay_sec',
        'speed_kmh',
        'occupancy_percent'
    ]
    
    # 导入 numpy 用于处理 NaN
    import numpy as np
    for col in mean_columns_to_clean:
        if col in df_detailed.columns:
            # 将字符串 ‘INF‘ 替换为 np.nan（Not a Number），求均值时会自动忽略
            df_detailed[col] = df_detailed[col].replace('INF', np.nan)
            # 确保该列数据类型为浮点数
            df_detailed[col] = pd.to_numeric(df_detailed[col], errors='coerce')
    
    # --- 定义聚合规则（保持不变）---
    agg_rules = {
        # 求和项
        'arrival_rate_alpha_veh_per_h': 'sum',
        'saturation_flow_beta_s_veh_per_h': 'sum',
        'capacity_beta_veh_per_h': 'sum',
        'nVehEntered': 'sum',
        'totalTimeLoss_sec': 'sum',
        # 极值项
        'observed_max_queue_m': 'max',
        'jamLength_veh': 'max',
        # 平均值项 - 现在可以安全计算了
        'degree_of_saturation_rho': 'mean',
        'rho_saturated_rho_s': 'mean',
        'uniform_delay_w_u_sec': 'mean',
        'random_delay_w_r_sec': 'mean',
        'total_delay_webster_sec': 'mean',
        'observed_avg_delay_sec': 'mean',
        'speed_kmh': 'mean',
        'occupancy_percent': 'mean',
    }
    
    # 仅选择数据框中实际存在的列进行聚合
    valid_agg_rules = {k: v for k, v in agg_rules.items() if k in df_detailed.columns}
    
    # --- 执行分组聚合 ---
    df_agg = df_detailed.groupby(['interval_begin', 'approach_flow']).agg(valid_agg_rules).reset_index()
    
    # 重新计算聚合后的饱和度（基于总和）更准确
    df_agg['degree_of_saturation_rho'] = df_agg['arrival_rate_alpha_veh_per_h'] / df_agg['capacity_beta_veh_per_h'].replace(0, np.nan)
    
    # 计算聚合后的平均延误（总延误时间/总车辆数）更准确
    df_agg['observed_avg_delay_sec_agg'] = df_agg['totalTimeLoss_sec'] / df_agg['nVehEntered'].replace(0, np.nan)
    
    # 分离方向和流向
    df_agg[['approach', 'flow_type']] = df_agg['approach_flow'].str.split('_', expand=True)
    
    # 重新排序列
    agg_columns = ['interval_begin', 'approach_flow', 'approach', 'flow_type',
                   'arrival_rate_alpha_veh_per_h', 'capacity_beta_veh_per_h',
                   'degree_of_saturation_rho', 'observed_max_queue_m',
                   'observed_avg_delay_sec_agg', 'total_delay_webster_sec',
                   'nVehEntered', 'totalTimeLoss_sec']
    
    available_cols = [col for col in agg_columns if col in df_agg.columns]
    df_agg = df_agg[available_cols]
    
    # 将最终结果中的 NaN 替换回 ‘INF‘ 或留空，以便阅读
    # df_agg = df_agg.fillna('INF')  # 可选：如果您希望结果中明确显示 INF
    
    return df_agg

def safe_float(value, default=0.0):
    try:
        return float(value) if value not in [None, ''] else default
    except (ValueError, TypeError):
        return default

def format_value(value, inf_str='INF'):
    if isinstance(value, str):
        return value
    if value == float('inf') or value == float('-inf'):
        return inf_str
    try:
        return round(value, 3)
    except (TypeError, ValueError):
        return value

if __name__ == "__main__":
    main()