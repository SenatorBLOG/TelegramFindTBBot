"""FSM states for the profile creation / editing wizard (9 steps)."""
from aiogram.fsm.state import State, StatesGroup


class ProfileFSM(StatesGroup):
    name = State()
    from_location = State()
    destination = State()
    dates = State()         # shows quick-pick buttons AND accepts free text
    budget = State()
    style = State()
    language = State()
    bio = State()
    photo = State()         # optional profile photo — final step, auto-fills contact
