import random

def check_probability_threshold(threshold: float = 0.5) -> tuple[bool, float]:
    """
    根据给定的概率阈值判断是否命中

    Args:
        threshold (float): 概率阈值，默认为0.5

    Returns:
        tuple[bool, float]: (是否命中阈值, 随机值)
            - bool: True表示随机值小于阈值(命中)，False表示未命中
            - float: 生成的随机值(0-1之间)
    """
    random_value = random.random()
    is_hit = random_value < threshold
    return is_hit, random_value