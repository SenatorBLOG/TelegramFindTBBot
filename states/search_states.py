"""FSM states for the guided search wizard."""
from aiogram.fsm.state import State, StatesGroup


class SearchFSM(StatesGroup):
    destination = State()
    date_range = State()
    budget = State()
    style = State()
    paging = State()      # results shown; filters kept in FSM data for pagination
