"""Console rendering for the deterministic DSS; no data retrieval."""

from services.dss_service import CATEGORY_LABELS, DSS_CATEGORIES, TOP_MOVE_COUNT, TOP_MOVE_DETAIL_COUNT


def record_text(record):
    return f"{record['wins']}-{record['losses']}-{record['ties']}"


def heading(text):
    print('\n' + '=' * 112)
    print(text)
    print('=' * 112)


def print_dss_report(report, notes=()):
    heading('DSS INPUT SUMMARY')
    for label, value in report['summary'].items():
        print(f'{label}: {value}')
    print('Seven-category projection only; FG% and FT% excluded. Positive gaps always favour you.')
    print('Assumes all remaining player appearances contribute; no lineup, injury or transaction constraints.')
    print('Schedule is calendar-date based; same-day moves count. No lineup-slot congestion, waiver delay, or lock-time modeling.')
    for note in notes:
        print(note)
    if report['partial_projection']:
        print('PARTIAL PROJECTION: roster players with missing data are omitted; rankings are provisional.')
    for skipped in report['skipped']:
        print(f"Skipped {skipped['group']}: {skipped['playerName']} ({'; '.join(skipped['reasons'])})")
    heading('LIVE MATCHUP OUTLOOK')
    print(f"{'CAT':<5} {'CURRENT ME/OPP':>19} {'REMAINING ME/OPP':>21} {'FINAL ME/OPP':>21} {'GAP':>10}  STATUS")
    for key, row in report['outlook'].items():
        current = f"{row['current_me']:.1f} / {row['current_opp']:.1f}"
        remaining = f"{row['remaining_me']:.1f} / {row['remaining_opp']:.1f}"
        final = f"{row['me']:.1f} / {row['opp']:.1f}"
        print(f"{CATEGORY_LABELS[key]:<5} {current:>19} {remaining:>21} {final:>21} {row['gap']:>+10.2f}  {row['status']}")
    print(f"\nProjected category record (W-L-T): {record_text(report['record'])}")
    print('Highest-priority categories: ' + ', '.join(
        f"{CATEGORY_LABELS[k]} ({report['outlook'][k]['status']})" for k in report['priorities'][:3]))
    heading('TOP STREAMING MOVES')
    print('Ranked by matchup impact after applying each move date to actual remaining game dates.')
    if not report['moves']:
        print('No eligible add/drop combinations. Keep the current roster.')
        return
    if report['moves'][0]['impact_score'] <= 0:
        print('No positive-impact move found. Keeping the current roster is preferred.')
    print(f"{'RANK':<5} {'ADD PLAYER':<30} {'DROP PLAYER':<30} {'MOVE DATE':<12} {'NET GAMES':>9} {'SCORE':>9}")
    for rank, move in enumerate(report['moves'][:TOP_MOVE_COUNT], 1):
        print(f"{rank:<5} {move['add_player']['playerName']:<30} {move['drop_player']['playerName']:<30} "
              f"{move['move_date']:<12} {move['net_games']:>+9} {move['impact_score']:>9.3f}")
    for rank, move in enumerate(report['moves'][:TOP_MOVE_DETAIL_COUNT], 1):
        heading(f'MOVE #{rank} DETAILS')
        for action, player in [('ADD', move['add_player']), ('DROP', move['drop_player'])]:
            print(f"{action}: {player['playerName']} | Team: {player['nba_team']}")
        print(f"MAKE MOVE: {move['move_date']}")
        print(f"ADD PLAYER USABLE GAMES ({move['add_usable_games']}): "
              f"{', '.join(move['add_usable_game_dates']) or 'none'}")
        print(f"DROP PLAYER LOST GAMES ({move['drop_lost_games']}): "
              f"{', '.join(move['drop_lost_game_dates']) or 'none'}")
        print(f"NET GAMES: {move['net_games']:+d}")
        print('\nNET REMAINING PRODUCTION (positive TO means more turnovers)')
        for key in DSS_CATEGORIES:
            print(f"{CATEGORY_LABELS[key]:<5} {move['net_production'][key]:+9.2f}")
        print('\nMATCHUP EFFECT (positive change helps, including TO)')
        print(f"{'CAT':<5} {'BEFORE GAP':>12} {'AFTER GAP':>12} {'CHANGE':>12}")
        for key, effect in move['effects'].items():
            print(f"{CATEGORY_LABELS[key]:<5} {effect['before_gap']:>+12.2f} "
                  f"{effect['after_gap']:>+12.2f} {effect['gap_change']:>+12.2f}")
        print('\nSTATUS CHANGES')
        for key, (before, after) in move['transitions'].items():
            print(f'{CATEGORY_LABELS[key]}: {before} -> {after}')
        if not move['transitions']:
            print('None')
        print(f"PROJECTED RECORD: {record_text(move['before_record'])} -> {record_text(move['after_record'])}")
        before, after = move['before_record'], move['after_record']
        improved = (after['wins'], -after['losses']) > (before['wins'], -before['losses'])
        print(f"Category record improves: {'YES' if improved else 'NO'}")
        print(f"MATCHUP IMPACT SCORE: {move['impact_score']:.3f}")
