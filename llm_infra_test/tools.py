"""
Simple tools for testing LLM function calling.
"""

import random
import datetime
import math

# ============================================================================
# Tool definitions (OpenAI format)
# ============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'Beijing', 'Shanghai'",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a math expression and return the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. '2 + 3 * 4', 'sqrt(144)', 'pi * 2'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time, optionally for a timezone offset",
            "parameters": {
                "type": "object",
                "properties": {
                    "utc_offset": {
                        "type": "integer",
                        "description": "UTC offset in hours, e.g. 8 for Beijing, -5 for New York. Defaults to 8 (Beijing).",
                    },
                },
            },
        },
    },
]


# ============================================================================
# Tool implementations
# ============================================================================

MOCK_WEATHER = {
    "beijing": {"temp": 22, "condition": "sunny", "humidity": 35},
    "shanghai": {"temp": 26, "condition": "cloudy", "humidity": 65},
    "guangzhou": {"temp": 30, "condition": "rainy", "humidity": 80},
    "shenzhen": {"temp": 29, "condition": "partly cloudy", "humidity": 72},
    "hangzhou": {"temp": 24, "condition": "overcast", "humidity": 58},
}


def get_weather(city: str) -> dict:
    key = city.lower().strip()
    if key in MOCK_WEATHER:
        data = MOCK_WEATHER[key]
    else:
        data = {
            "temp": random.randint(10, 35),
            "condition": random.choice(["sunny", "cloudy", "rainy", "windy"]),
            "humidity": random.randint(20, 90),
        }
    return {"city": city, **data}


SAFE_MATH = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "pow": pow,
}


def calculate(expression: str) -> dict:
    try:
        result = eval(expression, {"__builtins__": {}}, SAFE_MATH)
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"expression": expression, "error": str(exc)}


def get_current_time(utc_offset: int = 8) -> dict:
    tz = datetime.timezone(datetime.timedelta(hours=utc_offset))
    now = datetime.datetime.now(tz)
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": f"UTC{utc_offset:+d}",
    }


# name -> callable mapping
TOOL_EXECUTORS = {
    "get_weather": lambda args: get_weather(args["city"]),
    "calculate": lambda args: calculate(args["expression"]),
    "get_current_time": lambda args: get_current_time(args.get("utc_offset", 8)),
}
