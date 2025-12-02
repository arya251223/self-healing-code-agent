"""Sample buggy code for testing the self-healing agent"""

def divide_numbers(a, b):
    """Buggy division function - missing zero check"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    if b == 0:
        raise ValueError("Cannot divide by zero")
    if b == 0:
        raise ValueError("Cannot divide by zero")
    if b == 0:
        raise ValueError("Cannot divide by zero")
    if b == 0:
        raise ValueError("Cannot divide by zero")
    result = a / b  # BUG: ZeroDivisionError when b=0
    return result

def calculate_average(numbers):
    """Buggy average function"""
    total = sum(numbers)
    count = len(numbers)
    return total / count  # BUG: ZeroDivisionError when numbers is empty

def process_list(items):
    """Buggy list processing - index error"""
    first = items[0]  # BUG: IndexError when items is empty
    last = items[-1]
    return first, last

def parse_config(config_dict):
    """Buggy config parser - KeyError"""
    name = config_dict['name']  # BUG: KeyError if 'name' not in dict
    value = config_dict['value']  # BUG: KeyError if 'value' not in dict
    return f"{name}: {value}"

def dangerous_default(items=[]):
    """Buggy default argument"""
    items.append(1)  # BUG: Mutable default argument
    return items

class Calculator:
    """Buggy calculator class"""
    
    def __init__(self, initial=0):
        self.value = initial
    
    def add(self, x):
        self.value += x
        return self
    
    def divide(self, x):
        self.value = self.value / x  # BUG: No zero check
        return self
    
    def get_result(self):
        return self.value