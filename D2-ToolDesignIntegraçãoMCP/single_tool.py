import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

api_key = os.environ["ANTHROPIC_API_KEY"]

client = anthropic.Anthropic(api_key=api_key)


# Ring 1: Single tool, single turn.
tools1 = [
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
    tools=tools1,
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
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools1,
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

# What to expect

# Output
# stop_reason: tool_use
# Tool: create_calendar_event
# Input: {'title': 'Sync', 'start': '2026-03-30T10:00:00', 'end': '2026-03-30T10:30:00', 'attendees': ['alice@example.com', 'bob@example.com']}
# stop_reason: end_turn
# I've scheduled your 30-minute sync with Alice and Bob for Monday, March 30 at 10am.


# Ring 2: The agentic loop.

tools2 = [
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
    tools=tools2,
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
        tools=tools2, 
        tool_choice={"type": "auto", "disable_parallel_tool_use": True},
        messages=messages
    )
    
    
    final_text = next(block for block in response.content if block.type == "text")
    print(final_text.text)

# What to expect
# Output
# I've set up your weekly team standup for the next 4 Mondays at 9am with Alice, Bob, and Carol invited.

# Ring 3: Multiple tools, parallel calls.

tools3 = [
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

def run_tool(name, tool_input):
    if name == "create_calendar_event":
        if "attendees" in tool_input and len(tool_input["attendees"]) > 10:
            raise ValueError("Too many attendees (max 10)")
        return {"event_id": "evt_123", "status": "created", "title": tool_input["title"]}
    if name == "list_calendar_events":
        return {"events": [{"title": "Existing meeting", "start": "14:00", "end": "15:00"}]}
    raise ValueError(f"Unknown tool: {name}")
    

messages = [
    {
        "role": "user",
        "content": "Schedule an all-hands with everyone: " + ", ".join(f"user{i}@exemple.com" for i in range(15)),
    }
]

reponse = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    tools=tools3,
    messages=messages
)

while reponse.sttop_reason == "tool_use":
    tool_results = []
    for block in response.contentL:
        if block.type == "tool_use":
            try:
                result = run_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result", 
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    }
                )
            except Exception as exc:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(exc),
                        "is_error": True,
                    }
                )
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})

    reponse = client.messages.create(
        model ="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=tools3,
        messages=messages,
    )
    
final_text = next(block for block in response.content if block.type == "text")
print(final_text.text)



# What to expect
# I checked your calendar for next Monday and found an existing meeting from 2pm to 3pm. 
# I've scheduled the planning session for 10am to 11am to avoid the conflict.
    
    
# Ring 4: Error handling.

tools4 = [
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


def run_tool(name, tool_input):
    if name == "create_calendar_event":
        if "attendees" in tool_input and len(tool_input["attendees"]) > 10:
            raise ValueError("Too many attendees (max 10)")
        return ValueError("Too many attendees (max 10)")
    if name == "list_ccalender_events":
        return {"events": [{"title": "Existin meeting", "start": "14:00", "end": "15:00"}]}
    raise ValueError(f"Unknown tool: {name}")
                     

massages = [
    {
        "role": "user",
        "content": "Schedule an all-hands with everyone: " + ", ".join(f"user{i}@exemple.com" for i in range(15)),
    }
]
                     


# What to expect
# I tried to schedule the all-hands but the calendar only allows 10 attendees per event. 
# I can split this into two sessions, or you can let me know which 10 people to prioritize.



# Ring 5: The Tool Runner SDK abstraction.
from anthropic import beta_tool

@beta_tool
def create_calendar_event(
    title: str,
    start: str,
    end: str,
    attendees: list[str] | None = None
) -> str:
    """Create a calendar event with attendees and optional recurrence.

    Args:
        title: Event title.
        start: Start time in ISO 8601 format.
        end: End time in ISO 8601 format.
        attendees: Email addresses to invite.
        recurrence: Dict with 'frequency' (daily, weekly, monthly) and 'count'.
    """
    if attendees and len(attendees) > 10:
        raise ValueError("Too many attendees (max 10)")
    return json.dumps({"event_id": "evt_123", "status": "created", "title": title})


@beta_tool
def list_calendar_events(date: str) -> str:
    """List all calendar events on a given date.

    Args:
        date: Date in YYYY-MM-DD format.
    """
    return json.dumps({"events": [{"title": "Existing meeting", "start": "14:00", "end": "15:00"}]})


final_message = client.beta.messages.tool_runner(
    model="claude-opus-5",
    max_tokens=1024,
    tools=[create_calendar_event, list_calendar_events],
    messages=[
        {
            "role": "user",
            "content": "Check what I have next Monday, then schedule a planning session that avoids any conflicts.",
        }
    ],
).until_done()

for block in final_message.content:
    if block.type == "text":
        print(block.text)
        
        
# What to expect

# Output
# I checked your calendar for next Monday and found an existing meeting from 2pm to 3pm. I've scheduled the planning session for 10am to 11am to avoid the conflict.