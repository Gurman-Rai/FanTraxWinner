"""Run directly from any directory; fake dictionaries only, no API calls."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.dss_service import build_dss_report
from formatters.dss_formatter import print_dss_report


def fake_data():
    mine = [
        dict(playerName='My Star', nba_team='AAA', games_remaining=2, pts=25, reb=5,
             ast=6, stl=1, blk=0.5, fg3m=3, tov=2, adp=10),
        dict(playerName='My Streamer', nba_team='BBB', games_remaining=1, pts=10, reb=4,
             ast=2, stl=0.5, blk=0.2, fg3m=1, tov=1, adp=180),
    ]
    opponent = [dict(playerName='Opponent A', nba_team='CCC', games_remaining=2,
                     pts=20, reb=8, ast=4, stl=1, blk=1, fg3m=2, tov=2, adp=50)]
    waivers = [
        dict(playerName='Rebound Block Waiver', nba_team='DDD', games_remaining=3,
             pts=10, reb=10, ast=1, stl=0.8, blk=2, fg3m=0, tov=1, adp=150),
        dict(playerName='Scoring Guard Waiver', nba_team='EEE', games_remaining=3,
             pts=20, reb=2, ast=5, stl=0.5, blk=0, fg3m=4, tov=3, adp=130),
    ]
    score = {key: {'me': me, 'opp': opp} for key, me, opp in [
        ('pts', 400, 350), ('reb', 120, 130), ('ast', 90, 92),
        ('stl', 25, 24), ('blk', 15, 18), ('fg3m', 55, 40), ('tov', 45, 48)]}
    return score, mine, opponent, waivers


def main():
    report = build_dss_report(*fake_data())
    winner = report['moves'][0]
    assert winner['add_player']['playerName'] == 'Rebound Block Waiver'
    assert winner['drop_player']['playerName'] == 'My Streamer'
    assert winner['after_record']['wins'] >= winner['before_record']['wins']
    print('FAKE DSS SANITY CHECK')
    print_dss_report(report, ['Synthetic inputs only; no network calls.'])
    print('\nSANITY CHECK PASSED: Rebound Block Waiver ranks first.')


if __name__ == '__main__':
    main()
