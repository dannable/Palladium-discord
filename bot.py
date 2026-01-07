#!/usr/bin/env python3
import os
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Union

import discord
from discord import app_commands
from dotenv import load_dotenv

# -------------------- Env --------------------

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 30:
    raise RuntimeError("DISCORD_TOKEN looks missing/invalid. Put your Bot Token in .env as DISCORD_TOKEN=... (no quotes).")

# -------------------- Dice helpers --------------------

def roll_d6() -> int:
    return random.randint(1, 6)

def roll_d100() -> int:
    return random.randint(1, 100)

def roll_nds(n: int, s: int) -> int:
    return sum(random.randint(1, s) for _ in range(n))

def money(n: int, s: int, mult: int = 1, add: int = 0) -> int:
    return roll_nds(n, s) * mult + add

def fmt_cash(amount: Optional[int]) -> str:
    if amount is None:
        return "None"
    return f"${amount:,}"

# -------------------- Attribute rolling --------------------

def roll_attribute() -> int:
    # Base roll: 4d6 drop lowest
    rolls = sorted(roll_d6() for _ in range(4))
    total = sum(rolls[1:])

    # If 16–18 on the base, add bonus dice: +1d6; if that die is 6, +1d6 more (max 2)
    if 16 <= total <= 18:
        bonus1 = roll_d6()
        total += bonus1
        if bonus1 == 6:
            total += roll_d6()

    return total

def clamp_for_chart(score: int) -> int:
    return min(score, 30)

# -------------------- Palladium bonus tables (16..30) --------------------

MA_TRUST_INTIMIDATE = {
    16: 40, 17: 45, 18: 50, 19: 55, 20: 60,
    21: 65, 22: 70, 23: 75, 24: 80, 25: 84,
    26: 88, 27: 92, 28: 94, 29: 96, 30: 97
}

PE_COMA_DEATH = {
    16: 4, 17: 5, 18: 6, 19: 8, 20: 10,
    21: 12, 22: 14, 23: 16, 24: 18, 25: 20,
    26: 22, 27: 24, 28: 26, 29: 28, 30: 30
}

PB_CHARM_IMPRESS = {
    16: 30, 17: 35, 18: 40, 19: 45, 20: 50,
    21: 55, 22: 60, 23: 65, 24: 70, 25: 75,
    26: 80, 27: 83, 28: 86, 29: 90, 30: 92
}

def iq_bonus_percent(iq: int) -> int:
    if iq < 16:
        return 0
    return clamp_for_chart(iq) - 14  # 16->2 ... 30->16

def step_every_two(score: int) -> int:
    if score < 16:
        return 0
    return (clamp_for_chart(score) - 14) // 2  # 16->1 ... 30->8

def me_insanity_bonus(me: int) -> int:
    if me < 16:
        return 0
    s = clamp_for_chart(me)
    if s <= 20:
        return (s - 14) // 2
    return s - 17  # 21->4 ... 30->13

def ps_damage_bonus(ps: int) -> int:
    if ps < 16:
        return 0
    return clamp_for_chart(ps) - 15  # 16->1 ... 30->15

def ma_trust_intimidate_percent(ma: int) -> int:
    if ma < 16:
        return 0
    return MA_TRUST_INTIMIDATE[clamp_for_chart(ma)]

def pe_coma_death_percent(pe: int) -> int:
    if pe < 16:
        return 0
    return PE_COMA_DEATH[clamp_for_chart(pe)]

def pb_charm_impress_percent(pb: int) -> int:
    if pb < 16:
        return 0
    return PB_CHARM_IMPRESS[clamp_for_chart(pb)]

def format_attr_line(attr: str, score: int) -> str:
    capped_note = " (bonuses capped @30)" if score > 30 else ""
    parts: List[str] = []

    if attr == "IQ":
        bonus = iq_bonus_percent(score)
        if bonus:
            parts.append(f"Skills +{bonus}%")

    elif attr == "ME":
        psionic = step_every_two(score)
        insanity = me_insanity_bonus(score)
        if psionic:
            parts.append(f"Save vs Psionic +{psionic}")
        if insanity:
            parts.append(f"Save vs Insanity +{insanity}")

    elif attr == "MA":
        pct = ma_trust_intimidate_percent(score)
        if pct:
            parts.append(f"Trust/Intimidate {pct}%")

    elif attr == "PS":
        dmg = ps_damage_bonus(score)
        if dmg:
            parts.append(f"Damage +{dmg}")

    elif attr == "PP":
        pd = step_every_two(score)
        if pd:
            parts.append(f"Parry/Dodge +{pd}")
            parts.append(f"Strike +{pd}")

    elif attr == "PE":
        coma = pe_coma_death_percent(score)
        mp = step_every_two(score)
        if coma:
            parts.append(f"Save vs Coma/Death +{coma}%")
        if mp:
            parts.append(f"Save vs Magic/Poison +{mp}")

    elif attr == "PB":
        pct = pb_charm_impress_percent(score)
        if pct:
            parts.append(f"Charm/Impress {pct}%")

    elif attr == "SPD":
        pass

    if parts:
        return f"{attr}: {score} ({', '.join(parts)}){capped_note}"
    return f"{attr}: {score}{capped_note}"

# -------------------- Animal tables --------------------

RangeTable = List[Tuple[int, int, str]]

ANIMAL_CATEGORY: RangeTable = [
    (1, 15, "Urban"),
    (16, 25, "Rural"),
    (26, 45, "Forest"),
    (46, 70, "Desert/Plains"),
    (71, 75, "Aquatic"),
    (76, 95, "Wild Birds"),
    (96, 100, "Zoo"),
]

ANIMALS_BY_CATEGORY: Dict[str, RangeTable] = {
    "Urban": [
        (1, 25, "Dog"), (26, 45, "Cat"), (46, 50, "Mouse"), (51, 55, "Rat"),
        (56, 58, "Hamster"), (59, 60, "Guinea Pig"), (61, 65, "Squirrel"),
        (66, 75, "Sparrow"), (76, 83, "Pigeon"), (84, 85, "Parrot"),
        (86, 88, "Bat"), (89, 92, "Turtle"), (93, 95, "Frog"),
        (96, 97, "Lizard"), (98, 100, "Chameleon"),
    ],
    "Rural": [
        (1, 10, "Dog"), (11, 15, "Cat"), (16, 20, "Cow"), (21, 35, "Pig"),
        (36, 45, "Chicken"), (46, 50, "Duck"), (51, 58, "Horse"),
        (59, 62, "Donkey"), (63, 65, "Rabbit"), (66, 75, "Mouse"),
        (76, 80, "Jumping Mouse"), (81, 85, "Sheep"), (86, 90, "Goat"),
        (91, 94, "Turkey"), (95, 100, "Bat"),
    ],
    "Forest": [
        (1, 3, "Wolf"), (4, 6, "Fox"), (7, 13, "Coyote"), (14, 16, "Badger"),
        (17, 20, "Black Bear"), (21, 24, "Grizzly Bear"), (25, 30, "Mountain Lion"),
        (31, 32, "Bobcat"), (33, 34, "Lynx"), (35, 36, "Wolverine"),
        (37, 40, "Weasel"), (41, 45, "Raccoon"), (46, 54, "Ringtail"),
        (55, 60, "Opossum"), (61, 65, "Skunk"), (66, 70, "Porcupine"),
        (71, 76, "Mole"), (77, 78, "Squirrel"), (79, 84, "Marten"),
        (85, 94, "Deer"), (95, 100, "Elk"),
    ],
    "Desert/Plains": [
        (1, 15, "Coyote"), (16, 20, "Mountain Lion"), (21, 30, "Armadillo"),
        (31, 35, "Peccary (treat as a Boar)"), (36, 40, "Coati"),
        (41, 45, "Gila Monster"), (46, 55, "Lizard"), (56, 65, "Pack Rat"),
        (66, 75, "Prairie Dog"), (76, 80, "Pronghorn"), (81, 90, "Road Runner"),
        (91, 95, "Kangaroo Rat"), (96, 100, "Jumping Mouse"),
    ],
    "Aquatic": [
        (1, 20, "Otter"), (21, 30, "Beaver"), (31, 50, "Muskrat"),
        (51, 55, "Dolphin"), (56, 60, "Whale"), (61, 65, "Octopus"),
        (66, 70, "Sea Turtle"), (71, 80, "Sea Lion"), (81, 90, "Seal"),
        (91, 100, "Walrus"),
    ],
    "Wild Birds": [
        (1, 10, "Sparrow"), (11, 15, "Robin"), (16, 18, "Blue Jay"),
        (19, 21, "Cardinal"), (22, 23, "Wild Turkey"), (24, 25, "Pheasant"),
        (26, 27, "Grouse"), (28, 29, "Quail"), (30, 34, "Crow"),
        (35, 39, "Duck"), (40, 45, "Owl"), (46, 50, "Condor"),
        (51, 55, "Buzzard"), (56, 65, "Vulture"), (66, 70, "Hawk"),
        (71, 75, "Falcon"), (76, 85, "Goose"), (86, 90, "Eagle"),
        (91, 100, "Hummingbird"),
    ],
    "Zoo": [
        (1, 10, "Lion"), (11, 15, "Tiger"), (16, 20, "Leopard"),
        (21, 25, "Cheetah"), (26, 30, "Polar Bear"),
        (31, 35, "Crocodile (or Alligator)"), (36, 40, "Aardvark"),
        (41, 45, "Rhinoceros"), (46, 50, "Hippopotamus"),
        (51, 60, "Elephant"), (61, 65, "Chimpanzee"), (66, 70, "Orangutan"),
        (71, 75, "Gorilla"), (76, 85, "Monkey"), (86, 90, "Baboon"),
        (91, 95, "Camel"), (96, 100, "Buffalo"),
    ],
}

def pick_from_table(roll: int, table: RangeTable) -> str:
    for lo, hi, value in table:
        if lo <= roll <= hi:
            return value
    raise ValueError(f"No match for roll {roll} in table")

def generate_animal_type() -> dict:
    cat_roll = roll_d100()
    category = pick_from_table(cat_roll, ANIMAL_CATEGORY)
    animal_roll = roll_d100()
    animal = pick_from_table(animal_roll, ANIMALS_BY_CATEGORY[category])
    return {"category_roll": cat_roll, "category": category, "animal_roll": animal_roll, "animal": animal}

# -------------------- Mutant Background --------------------

MUTANT_BACKGROUND: RangeTable = [
    (1, 15, "Mechanic"),
    (16, 35, "Biker"),
    (36, 45, "Trooper"),
    (46, 55, "Feral Mutant Animal"),
    (56, 75, "Ninja"),
    (76, 85, "Trucker"),
    (86, 95, "Highway Engineer"),
    (96, 100, "Natural Mechanical Genius"),
]

MUTANT_BACKGROUND_SUMMARY: Dict[str, str] = {
    "Mechanic": "Garage-trained; strong repair/diagnostics focus; significant vehicle expense (car build).",
    "Biker": "Biker-gang upbringing; strong piloting/combat; revenge is common.",
    "Trooper": "Road Patrol tradition; military-style training; law & order focus.",
    "Feral Mutant Animal": "Wilderness survivor; tougher/rougher; no vehicle expense.",
    "Ninja": "Adopted into a ninja school; stealth & martial training; teacher provides a quality weapon.",
    "Trucker": "Armed convoy specialist; freight truck piloting; defends the highways.",
    "Highway Engineer": "Road/bridge/tunnel specialist; engineering & heavy machinery; respected trade.",
    "Natural Mechanical Genius": "Innate machine intuition; fixes may fail when you leave the machine’s vicinity.",
}

def generate_mutant_background() -> dict:
    roll = roll_d100()
    background = pick_from_table(roll, MUTANT_BACKGROUND)
    return {"roll": roll, "background": background, "summary": MUTANT_BACKGROUND_SUMMARY.get(background, "")}

# -------------------- Finances (vehicle expenses + personal money) --------------------

@dataclass(frozen=True)
class DiceMoney:
    n: int
    s: int
    mult: int = 1
    add: int = 0

PersonalMoneyRule = Union[DiceMoney, int, None]  # None means "none/handled as gear-only text"

BACKGROUND_FINANCES: Dict[str, Dict[str, object]] = {
    # From your Mutant Background chart text (as readable on the scan):
    "Mechanic": {
        "personal_rule": DiceMoney(3, 6, 100),   # $300–$1800
        "vehicle_expenses": 12000,              # "$12,000 car"
        "personal_note": None,
    },
    "Biker": {
        "personal_rule": DiceMoney(2, 6, 100),  # $200–$1200
        "vehicle_expenses": 6000,
        "personal_note": None,
    },
    "Trooper": {
        "personal_rule": DiceMoney(3, 6, 100),  # $300–$1800
        "vehicle_expenses": 10000,
        "personal_note": None,
    },
    "Feral Mutant Animal": {
        "personal_rule": DiceMoney(1, 6, 10),   # $10–$60
        "vehicle_expenses": None,               # NO vehicle expenses
        "personal_note": None,
    },
    "Ninja": {
        "personal_rule": 250,                   # treat outfit money as personal gear budget
        "vehicle_expenses": None,
        "personal_note": "Outfitting budget (weapons/equipment/supplies).",
    },
    "Trucker": {
        "personal_rule": DiceMoney(2, 6, 100),  # $200–$1200
        "vehicle_expenses": 15000,
        "personal_note": None,
    },
    "Highway Engineer": {
        "personal_rule": DiceMoney(4, 6, 100),  # $400–$2400
        "vehicle_expenses": 8000,
        "personal_note": None,
    },
    "Natural Mechanical Genius": {
        "personal_rule": DiceMoney(2, 6, 10),   # $20–$120
        "vehicle_expenses": 2000,
        "personal_note": None,
    },
}

def generate_finances(background_name: str) -> dict:
    cfg = BACKGROUND_FINANCES.get(background_name)
    if not cfg:
        return {
            "personal_money": None,
            "personal_roll": None,
            "personal_note": "No finance rule configured.",
            "vehicle_expenses": None,
        }

    rule: PersonalMoneyRule = cfg["personal_rule"]  # type: ignore[assignment]
    personal_note: Optional[str] = cfg.get("personal_note")  # type: ignore[assignment]
    vehicle_expenses: Optional[int] = cfg.get("vehicle_expenses")  # type: ignore[assignment]

    if isinstance(rule, DiceMoney):
        raw = roll_nds(rule.n, rule.s)
        amount = raw * rule.mult + rule.add
        personal_roll = f"{rule.n}d{rule.s}={raw} → {fmt_cash(amount)}"
        personal_money = amount
    elif isinstance(rule, int):
        personal_money = rule
        personal_roll = fmt_cash(rule)
    else:
        personal_money = None
        personal_roll = None

    return {
        "personal_money": personal_money,
        "personal_roll": personal_roll,
        "personal_note": personal_note,
        "vehicle_expenses": vehicle_expenses,
    }

# -------------------- Character generation / formatting --------------------

def generate_character() -> tuple[Dict[str, int], dict, dict, dict]:
    attrs = ["IQ", "ME", "MA", "PS", "PP", "PE", "PB", "SPD"]
    scores = {a: roll_attribute() for a in attrs}
    animal = generate_animal_type()
    background = generate_mutant_background()
    finances = generate_finances(background["background"])
    return scores, animal, background, finances

def build_sheet_text(
    scores: Dict[str, int],
    animal: dict,
    background: dict,
    finances: dict,
    name: Optional[str] = None
) -> str:
    lines: List[str] = []

    if name:
        lines.append(f"**{name}**")

    lines.append("**Attributes**")
    for attr in ["IQ", "ME", "MA", "PS", "PP", "PE", "PB", "SPD"]:
        lines.append(format_attr_line(attr, scores[attr]))

    lines.append("")
    lines.append(
        f"**Animal Type**: {animal['animal']} "
        f"(Category: {animal['category']}; rolls {animal['category_roll']}/{animal['animal_roll']})"
    )

    lines.append("")
    lines.append(f"**Mutant Background**: {background['background']} (roll {background['roll']})")
    if background.get("summary"):
        lines.append(f"*{background['summary']}*")

    lines.append("")
    lines.append("**Finances**")
    pm = finances.get("personal_money")
    pr = finances.get("personal_roll")
    pn = finances.get("personal_note")
    ve = finances.get("vehicle_expenses")

    if pm is None and pr is None:
        lines.append("Personal Money: None/Unknown")
    else:
        lines.append(f"Personal Money: {fmt_cash(pm)}" + (f" ({pr})" if pr else ""))

    if pn:
        lines.append(f"*{pn}*")

    lines.append(f"Vehicle Expenses: {fmt_cash(ve)}")

    return "\n".join(lines)

def build_midjourney_prompt(
    animal: dict,
    background: dict,
    name: Optional[str] = None,
) -> str:
    """
    Returns a Midjourney-ready prompt string using Animal Type + Mutant Background.
    You can tweak style flags at the bottom to taste.
    """
    animal_type = animal["animal"]
    category = animal["category"]
    bg = background["background"]

    # Core concept line
    subject = f"anthropomorphic {animal_type.lower()} mutant"

    # Background flavor -> quick visual cues
    bg_flavor = {
        "Mechanic": "grease-stained coveralls, tool belt, welding goggles, patched leather jacket, improvised armor plates",
        "Biker": "spiked leathers, biker gang patches, road-worn helmet, chain accessories, sawed-off highway gear aesthetic",
        "Trooper": "wasteland highway patrol uniform, battered riot gear, tactical harness, badge, cracked visor helmet",
        "Feral Mutant Animal": "ragged scavenger wraps, survivalist straps, bone-and-scrap trophies, wild eyes, feral posture",
        "Ninja": "tattered ninja gi, wrapped hands, stealth harness, smoke bombs, subtle clan markings, masked face",
        "Trucker": "heavy-duty gloves, reinforced vest, cargo straps, trucker cap or helmet, convoy escort gear",
        "Highway Engineer": "utility harness, reflective strips, heavy boots, surveyor kit, roadwork tools, patched hardhat",
        "Natural Mechanical Genius": "improvised tech accessories, scavenged circuit charms, magnetized tool pouches, uncanny tinkerer vibe",
    }.get(bg, "post-apocalyptic scavenger gear, practical road-worn outfit")

    # Optional extras based on category for environment hints
    env_hint = {
        "Urban": "ruined city streets, graffiti, broken neon signs",
        "Rural": "dusty backroads, abandoned barns, telephone poles",
        "Forest": "overgrown highways, fallen pines, foggy treeline",
        "Desert/Plains": "sun-bleached asphalt, heat haze, windblown dust",
        "Aquatic": "flooded roadway, rusted bridge, rain-slicked pavement",
        "Wild Birds": "open sky, broken overpass, swirling debris",
        "Zoo": "escaped menagerie vibe, shattered zoo gates, warning signs",
    }.get(category, "wasteland highway")

    # Title/name tag
    name_tag = f"{name}, " if name else ""

    # Assemble prompt
    prompt = (
        f"{name_tag}{subject}, {bg.lower()} background, {bg_flavor}, "
        f"post-apocalyptic highway wasteland, {env_hint}, "
        f"full-body character concept art, dynamic pose, expressive silhouette, "
        f"high detail, gritty 1980s paperback illustration vibe, muted dusty palette, "
        f"cinematic lighting, sharp linework, highly textured materials, "
        f"clean background separation, character sheet presentation"
    )

    # Midjourney flags (tweak freely)
    flags = "--ar 2:3 --stylize 250 --v 6"

    return f"{prompt} {flags}"

# -------------------- Discord bot --------------------

class PalladiumBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if GUILD_ID:
            try:
                guild = discord.Object(id=int(GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"Synced commands to guild {GUILD_ID}")
                return
            except discord.Forbidden:
                print("Guild sync forbidden (Missing Access). Falling back to global sync...")
            except discord.HTTPException as e:
                print(f"Guild sync failed ({e}). Falling back to global sync...")

        await self.tree.sync()
        print("Synced commands globally (may take a while to appear).")

bot = PalladiumBot()

@bot.tree.command(
    name="palladium",
    description="Generate attributes + bonuses + animal type + mutant background + finances."
)
@app_commands.describe(name="Optional character name to include at the top")
async def palladium(interaction: discord.Interaction, name: Optional[str] = None):
    scores, animal, background, finances = generate_character()
    sheet = build_sheet_text(scores, animal, background, finances, name=name)
    await interaction.response.send_message(sheet)
@bot.tree.command(
    name="palladium_art",
    description="Generate the character + a Midjourney prompt based on animal type and background."
)
@app_commands.describe(
    name="Optional character name to include at the top (and in the art prompt)."
)
async def palladium_art(interaction: discord.Interaction, name: Optional[str] = None):
    scores, animal, background, finances = generate_character()
    sheet = build_sheet_text(scores, animal, background, finances, name=name)

    prompt = build_midjourney_prompt(animal, background, name=name)

    # Put the prompt in a code block for easy copying in Discord
    message = (
        f"{sheet}\n\n"
        f"**Midjourney Prompt**\n"
        f"```{prompt}```"
    )

    await interaction.response.send_message(message)
    
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
