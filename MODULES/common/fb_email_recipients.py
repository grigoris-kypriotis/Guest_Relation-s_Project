"""
Shared F&B email recipient lists for Offers and Cake Memo workflows.
=======================================================================
Centralizes the canonical recipient lists to prevent drift between
Offers and Cake Memo email distributions.
"""

# To Recipients: All F&B staff directly involved in order fulfillment
TO_RECIPIENTS = (
    "F&B Manager Sandy Beach <gabriela.stere@rizosresorts.gr>; "
    "Executive Chef Sandy Beach <chef.sandybeach@rizosresorts.gr>; "
    "headchef.sandybeach@rizosresorts.gr; "
    "assistfb.sandybeach@rizosresorts.gr; "
    "assistfb2.sandybeach@rizosresorts.gr;"
)

# CC Recipients: Operations and guest-facing staff who need visibility
CC_RECIPIENTS = (
    "Operation Manager <Mariela.Tsvetkova@rizosresorts.gr>; "
    "Rooms Division Manager - Sandy Beach <harrys.palikiras@rizosresorts.gr>; "
    "sfragoyiannis@rizosresorts.gr; "
    "Front Office Manager Sandy Beach <fom.sandy@rizosresorts.gr>; "
    "Guest Relations Sandy Beach <guest.sandybeach@rizosresorts.gr>;"
)
