import json
import anthropic

client = anthropic.Anthropic()

# Ring 1: Single tool, single turn.
tools = [
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event with attendees and optional recurrence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "format": "date-time"},
                "end": {"type": "string", "format": "date-time"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"},
                },
                "recurrence": {
                    "type": "object",
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "monthly"]},
                        "count": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "required": ["title", "start", "end"],
        },
    }
]

response = client.messages.create(
    model = "claude-sonnet-5",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type":"auto", "disable_parallel_tool_use": True},
    messages=[
        {
            "role": "user",
            "content": "Schedule a 30-minute sync with alice@example.com and bob@example.com on Monday, March 30, 2026 at 10am.",
        }
    ]
)


print(f"stop_reason: {response.stop_reason}")

tool_use = next(block for block in response.content if block.type == "tool_use")   
print(f"Tool: {tool_use.name}")
print(f"Input: {tool_use.input}")

result = {"event_id": "evt_123", "status": "created"}


followup = client.messages.create(
        model = "claude-sonnet-5",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type":"auto", "disable_parallel_tool_use": True},
    messages=[
        {
            "role": "user",
            "content": "Schedule a 30-minute sync with alice@example.com and bob@example.com on Monday, March 30, 2026 at 10am.",
        },
        {
            "role": "assistant", "content": response.content
        },
        {
            "user": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                }
              
            ]
        }
    ]
)

print(f"stop_reason: {followup.stop_reason}")
final_text = next(block for block in followup.content if block.type == "text")
print(final_text.text)


# Ring 2: The agentic loop.

tools = [
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event with attendees and optional recurrence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "format": "date-time"},
                "end": {"type": "string", "format": "date-time"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"},
                },
                "recurrence": {
                    "type": "object",
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "monthly"]},
                        "count": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "required": ["title", "start", "end"],
        },
    }
]

def run_tool(name, tool_input):
    if name == "create_calendar_event":
        return {"event_id": "evt_123", "status": "created", "title": tool_input["title"]}
    return {"error": f"Unkown tool: {name}"}

messages = [
    {
        "role": "user",
        "content": "Schedule a weekly team standup every Monday at 9am for the next 4 weeks. Invite the whole team: [email protected], [email protected], [email protected].",
    }
]

response = client.messages.create(
    model = "claude-sonnet-5",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type":"auto", "disable_parallel_tool_use": True},
    messages=messages
)

while response.stop_reason == "tool": 
    tool_use = next(block for block in response.content if block.type == "tool_use")   
    result = run_tool(tool_use.name, tool_use.input)
    
    messages.append({"role": "assistant", "content": response.content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                }
            ],
        }
    )
    
    response = client.messages.create(
        model = "claude-sonnet-5",
        max_tokens=1024,
        tools=tools, 
        tool_choice={"type": "auto", "disable_parallel_tool_use": True},
        messages=messages
    )
    
    
    final_text = next(block for block in response.content if block.type == "text")
    print(final_text.text)
    
    
    
# Ring 3: Multiple tools, parallel calls.

tools = [
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event with attendees and optional recurrence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "format": "date-time"},
                "end": {"type": "string", "format": "date-time"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"},
                },
                "recurrence": {
                    "type": "object",
                    "properties": {
                        "frequency": {"enum": ["daily", "weekly", "monthly"]},
                        "count": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "required": ["title", "start", "end"],
        },
    },
    {
        "name": "list_calendar_events",
        "description": "List all calendar events on a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
            },
            "required": ["date"],
        },
    },
]
