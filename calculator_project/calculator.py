class Calculator:
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b
    
    def multiply(self, a, b):
        return a * b
    
    def divide(self, a, b):
        try:
            return a / b
        except ZeroDivisionError:
            raise ValueError("Cannot divide by zero")

    def modulus(self, a, b):
        try:
            return a % b
        except ZeroDivisionError:
            raise ValueError("Cannot perform modulus with zero")