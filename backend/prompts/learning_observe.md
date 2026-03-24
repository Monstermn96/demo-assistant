---
id: learning_observe
name: Learning Observation Prompt
description: Template used when the learning agent observes a user-assistant interaction
agent: learning
---

Observe this interaction and decide if anything should be learned:

USER: {user_message}

ASSISTANT: {assistant_response}

If the user corrected the assistant, expressed a preference, or provided feedback, use the appropriate tool to record it. If the user indicated they want full cleanup when correcting (e.g. remove all duplicates, clean up completely), record that as a preference (e.g. key 'correction_cleanup' or 'cleanup_preference', value 'full cleanup'). If nothing notable happened, just respond with "Nothing to learn from this interaction."
