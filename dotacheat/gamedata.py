"""Small, hand-maintained game knowledge used by the heuristics.

Names are Dota 2 internal names (as they appear in replays). Lists are
deliberately conservative; they are easy to extend.
"""

# Defensive / escape responses whose timing after a threat is measured (heuristic b).
RESPONSES = {
    # items
    "item_blink", "item_overwhelming_blink", "item_swift_blink", "item_arcane_blink",
    "item_black_king_bar", "item_manta", "item_cyclone", "item_wind_waker", "item_lotus_orb",
    "item_glimmer_cape", "item_force_staff", "item_hurricane_pike", "item_ghost",
    "item_disperser", "item_minotaur_horn", "item_pipe", "item_crimson_guard",
    "item_satanic", "item_tpscroll", "item_travel_boots", "item_travel_boots_2",
    "item_sphere", "item_aeon_disk", "item_ethereal_blade", "item_bloodstone",
    "item_shadow_amulet", "item_invis_sword", "item_silver_edge", "item_eternal_shroud",
    "item_mjollnir", "item_harpoon", "item_book_of_shadows", "item_pavise",
    # abilities
    "antimage_blink", "queenofpain_blink", "puck_phase_shift", "puck_ethereal_jaunt",
    "slark_dark_pact", "slark_shadow_dance", "slark_depth_shroud", "juggernaut_blade_fury",
    "life_stealer_rage", "storm_spirit_ball_lightning", "ember_spirit_sleight_of_fist",
    "ember_spirit_activate_fire_remnant", "void_spirit_dissimilate", "void_spirit_astral_step",
    "weaver_shukuchi", "weaver_time_lapse", "phantom_lancer_doppelwalk",
    "naga_siren_mirror_image", "omniknight_repel", "omniknight_guardian_angel",
    "oracle_fates_edict", "oracle_false_promise", "abaddon_aphotic_shield",
    "abaddon_borrowed_time", "nyx_assassin_spiked_carapace", "nyx_assassin_vendetta",
    "templar_assassin_refraction", "templar_assassin_meld", "morphling_waveform",
    "faceless_void_time_walk", "faceless_void_time_walk_reverse", "dark_willow_shadow_realm",
    "bounty_hunter_wind_walk", "clinkz_wind_walk", "riki_tricks_of_the_trade",
    "mirana_leap", "sandking_burrowstrike", "earth_spirit_rolling_boulder",
    "pangolier_swashbuckle", "pangolier_gyroshell", "monkey_king_tree_dance",
    "monkey_king_mischief", "spectre_reality", "nature_prophet_teleportation",
    "furion_teleportation", "tinker_keen_teleport", "kunkka_x_marks_the_spot",
    "legion_commander_press_the_attack", "dazzle_shallow_grave", "winter_wyvern_cold_embrace",
    "batrider_firefly", "keeper_of_the_light_recall", "phoenix_icarus_dive",
    "magnataur_skewer", "rattletrap_hookshot", "tusk_snowball", "huskar_inner_fire",
    "medusa_stone_gaze", "arc_warden_magnetic_field", "doom_bringer_scorched_earth",
    "lone_druid_true_form_battle_cry", "brewmaster_primal_split", "troll_warlord_battle_trance",
    "ursa_enrage", "sven_warcry", "chaos_knight_phantasm", "terrorblade_reflection",
    "terrorblade_sunder", "invoker_ghost_walk", "invoker_tornado", "invoker_cold_snap",
    "shadow_demon_disruption", "obsidian_destroyer_astral_imprisonment",
    "rubick_telekinesis", "lion_voodoo", "shadow_shaman_voodoo",
}

# Enemy threats whose *cast order* starts the reaction clock (heuristic b).
THREATS = {
    "pudge_meat_hook", "mirana_arrow", "lion_impale", "lion_voodoo", "lion_finger_of_death",
    "lina_laguna_blade", "lina_light_strike_array", "shadow_shaman_voodoo",
    "shadow_shaman_shackles", "rubick_telekinesis", "batrider_flaming_lasso",
    "beastmaster_primal_roar", "magnataur_reverse_polarity", "enigma_black_hole",
    "faceless_void_chronosphere", "tidehunter_ravage", "axe_berserkers_call",
    "legion_commander_duel", "doom_bringer_doom", "bane_fiends_grip", "bane_nightmare",
    "earthshaker_fissure", "earthshaker_echo_slam", "sven_storm_bolt", "skeleton_king_hellfire_blast",
    "vengefulspirit_magic_missile", "chaos_knight_chaos_bolt", "dragon_knight_dragon_tail",
    "slardar_slithereen_crush", "centaur_hoof_stomp", "puck_dream_coil", "sand_king_burrowstrike",
    "sandking_burrowstrike", "tiny_avalanche", "tiny_toss", "kunkka_torrent", "kunkka_ghostship",
    "nyx_assassin_impale", "storm_spirit_electric_vortex", "ogre_magi_fireblast",
    "witch_doctor_paralyzing_cask", "jakiro_ice_path", "invoker_cold_snap", "invoker_tornado",
    "invoker_deafening_blast", "invoker_sun_strike", "invoker_emp", "invoker_chaos_meteor",
    "windrunner_shackleshot", "grimstroke_ink_creature", "grimstroke_soul_chain",
    "snapfire_mortimer_kisses", "snapfire_firesnap_cookie", "hoodwink_bushwhack",
    "marci_grapple", "dawnbreaker_fire_wreath", "primal_beast_onslaught", "primal_beast_pulverize",
    "muerta_dead_shot", "ringmaster_tame_the_beasts", "kez_grappling_claw",
    "item_sheepstick", "item_orchid", "item_bloodthorn", "item_abyssal_blade", "item_cyclone",
    "item_wind_waker", "item_rod_of_atos", "item_gungir", "item_nullifier", "item_ethereal_blade",
    "item_dagon", "item_dagon_2", "item_dagon_3", "item_dagon_4", "item_dagon_5",
    "item_blink", "item_overwhelming_blink", "item_swift_blink", "item_arcane_blink",
    "item_harpoon", "item_heavens_halberd",
}

# Skillshots for the dodge heuristic (d2): (ability, projectile speed, max range).
SKILLSHOTS = {
    "pudge_meat_hook": (1450.0, 1300.0),
    "mirana_arrow": (857.0, 3000.0),
    "windrunner_powershot": (3000.0, 2600.0),
    "rattletrap_hookshot": (4000.0, 2000.0),
    "earth_spirit_boulder_smash": (900.0, 2000.0),
    "vengefulspirit_wave_of_terror": (2000.0, 1400.0),
    "lion_impale": (1600.0, 725.0),
    "nyx_assassin_impale": (1600.0, 800.0),
    "jakiro_ice_path": (5000.0, 1200.0),
    "sandking_burrowstrike": (2000.0, 650.0),
    "magnataur_skewer": (1600.0, 1100.0),
    "tusk_ice_shards": (1200.0, 1700.0),
    "invoker_deafening_blast": (1100.0, 1000.0),
    "invoker_chaos_meteor": (300.0, 1100.0),
    "muerta_dead_shot": (2000.0, 1000.0),
    "hoodwink_bushwhack": (1300.0, 1000.0),
    "grimstroke_dark_artistry": (2400.0, 1400.0),
    "spirit_breaker_charge_of_darkness": (600.0, 99999.0),
}
