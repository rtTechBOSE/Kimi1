FUNCTION_CODE = {
    "set_lowLimit": 0x25,
    "set_highLimit": 0x26,
    "get_lowLimit": 0x25,
    "get_highLimit": 0x26,
    "enable_charge": 0x27,
    "led_ctl": 0x28,
    "set_mode": 0x29,
    "oqc_test": 0x30,
    "read_soc": 0x31,
    "read_curr": 0x32,
    "set_sleep_mode": 0x33,
    "battery_detect": 0x34,
    "get_mode": 0x35,
    "read_soh": 0x36,
    "read_id": 0x37,
    "read_sleep_mode": 0x38,
    "write_dlj_bytes": 0x39,
    "read_dlj_bytes": 0x3A,
    "read_voltage": 0x3B,
    "init_system": 0x3C,
}


def get_cmd_hex(cmd_str, slot, data=None):
    assert slot in [0x00, 0x01, 0x02, 0x03]
    # 0x25
    cmd_code = FUNCTION_CODE.get(cmd_str, None)
    if cmd_code:
        pass
    else:
        raise RuntimeError("cmd_str {} is avilad".format(cmd_str))

    if cmd_code in [0x31, 0x32, 0x34, 0x35, 0x36, 0x37, 0x38, 0x3A, 0x3B] or cmd_str== "get_lowLimit" or cmd_str == "get_highLimit":
        wr_code = 0x55
    else:
        wr_code = 0xAA
    
    if data is not None and isinstance(data, list):
        length = 0x04 + len(data)
        xor_code = 0x25^cmd_code^length^wr_code^slot
        for d in data:
            xor_code ^= d
        t = [0x25, cmd_code, length, wr_code, slot]
        t.extend(data)
        t.append(xor_code)
        t.append(0x0A)
    elif data is not None and isinstance(data, int):
        length = 0x05
        xor_code = 0x25^cmd_code^length^wr_code^slot
        t = [0x25, cmd_code, length, wr_code, slot]
        t.append(data)
        xor_code ^= data
        t.append(xor_code)
        t.append(0x0A)
    else:
        length = 0x04
        xor_code = 0x25^cmd_code^length^wr_code^slot
        t =  [0x25, cmd_code, length, wr_code, slot, xor_code, 0x0A]
    result = ' '.join(["{:02X}".format(hex_val) for hex_val in t])
    # print("{} : {}".format(cmd_str, result))
    return result


def show_menu():
    """显示指令菜单"""
    print("\n=== 指令选择菜单 ===")
    cmd_list = list(FUNCTION_CODE.keys())
    for i, cmd in enumerate(cmd_list, 1):
        print(f"{i}. {cmd}")
    print("0. 退出")
    return cmd_list

def get_user_input():
    """获取用户输入"""
    try:
        cmd_list = show_menu()
        
        # 选择指令
        while True:
            choice = input("\n请选择指令编号 (0-{}): ".format(len(cmd_list)))
            if choice == '0':
                print("退出程序")
                return None, None, None
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(cmd_list):
                    selected_cmd = cmd_list[choice_num - 1]
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入数字")
        
        # 选择通道
        while True:
            slot_input = input("请输入通道 (0-3): ")
            try:
                slot = int(slot_input)
                if slot in [0, 1, 2, 3]:
                    break
                else:
                    print("通道必须是 0, 1, 2, 3 中的一个")
            except ValueError:
                print("请输入数字")
        
        # 获取参数
        data = None
        if selected_cmd in ["read_soc", "read_curr", "battery_detect", "get_mode", "read_voltage"]:
            print("该指令无需参数")
        elif selected_cmd == "led_ctl":
            print("LED控制需要两个参数: [LED编号, 状态]")
            try:
                led_num = int(input("请输入LED编号 (0-2): "))
                led_state = int(input("请输入LED状态 (0=关闭, 1=开启): "))
                data = [led_num, led_state]
            except ValueError:
                print("参数输入错误，使用默认值 [0, 1]")
                data = [0, 1]
        else:
            param_input = input("请输入参数 (直接回车跳过): ")
            if param_input.strip():
                try:
                    # 尝试解析为整数
                    data = int(param_input)
                except ValueError:
                    # 尝试解析为列表
                    try:
                        data = eval(param_input)
                        if not isinstance(data, (int, list)):
                            print("参数格式错误，忽略参数")
                            data = None
                    except:
                        print("参数格式错误，忽略参数")
                        data = None
        
        return selected_cmd, slot, data
    
    except KeyboardInterrupt:
        print("\n用户取消操作")
        return None, None, None

def main():
    """主函数"""
    print("欢迎使用指令生成工具！")
    
    while True:
        cmd_str, slot, data = get_user_input()
        
        if cmd_str is None:
            break
        
        try:
            print("\n=== 生成结果 ===")
            result = get_cmd_hex(cmd_str, slot, data)
            print(f"十六进制指令: {result}")
            print("=" * 50)
            
            # 询问是否继续
            continue_choice = input("\n是否继续生成其他指令？(y/n): ")
            if continue_choice.lower() not in ['y', 'yes', '是']:
                break
                
        except Exception as e:
            print(f"错误: {e}")
            continue
    
    print("程序结束，感谢使用！")

if __name__ == "__main__":
    main()
