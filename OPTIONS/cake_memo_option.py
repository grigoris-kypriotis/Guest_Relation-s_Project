"""
Cake Memo Option: Re-export facade.
=====================================
Maintains backward-compatible API access. Delegates to:
  - OPTIONS.cake_memo.widget (CakeMemoOptionWidget)
  - OPTIONS.cake_memo.email_payload (generate_cake_memo_outlook_payload)
"""
from OPTIONS.cake_memo.widget import CakeMemoOptionWidget
from OPTIONS.cake_memo.email_payload import generate_cake_memo_outlook_payload

__all__ = ["CakeMemoOptionWidget", "generate_cake_memo_outlook_payload"]
