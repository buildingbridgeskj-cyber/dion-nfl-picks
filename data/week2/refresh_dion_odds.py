#!/usr/bin/env python3
"""Refresh Agent Dion's NFL board from The Odds API, then run the analysis."""
import csv, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
API = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
TEAM = {
 "Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF",
 "Carolina Panthers":"CAR","Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE",
 "Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET","Green Bay Packers":"GB",
 "Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC",
 "Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LAR","Miami Dolphins":"MIA",
 "Minnesota Vikings":"MIN","New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG",
 "New York Jets":"NYJ","Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF",
 "Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN","Washington Commanders":"WAS"
}
PROP_MAP={"player_pass_yds":"pass_yards","player_rush_yds":"rush_yards","player_reception_yds":"rec_yards"}

def get(path, params):
    key=os.environ.get("ODDS_API_KEY")
    if not key: raise SystemExit("ODDS_API_KEY is not set. Run: source ~/.bashrc")
    params={**params,"apiKey":key}
    with urlopen(f"{API}/{path}?{urlencode(params)}",timeout=45) as r:
        return json.load(r), r.headers.get("x-requests-remaining","unknown")

def dk_markets(event):
    book=next((b for b in event.get("bookmakers",[]) if b.get("key")=="draftkings"),None)
    return {m["key"]:m for m in (book or {}).get("markets",[])}

def roster():
    out={}
    for p in INPUTS.glob("*player_props*.csv"):
        with p.open(newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f): out[r.get("player","").strip()]=r.get("team","").strip()
    return out

def main():
    now=datetime.now(ZoneInfo("America/New_York")); date=now.date().isoformat()
    games,remaining=get(f"sports/{SPORT}/odds/",{"bookmakers":"draftkings","markets":"h2h,spreads,totals","oddsFormat":"american","dateFormat":"iso"})
    games=[g for g in games if datetime.fromisoformat(g["commence_time"].replace("Z","+00:00")).astimezone(ZoneInfo("America/New_York")).date().isoformat()==date]
    if not games: raise SystemExit(f"No unstarted DraftKings NFL games returned for {date} ET.")
    lines=INPUTS/f"week2_sunday_game_lines_api_{date}.csv"; props=INPUTS/f"week2_sunday_player_props_api_{date}.csv"; tds=INPUTS/f"week2_sunday_touchdowns_api_{date}.csv"
    with lines.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["kickoff_et","away_team","home_team","home_spread","total","away_ml","home_ml","neutral","source"]); w.writeheader()
        for g in games:
            m=dk_markets(g); home=g["home_team"]; away=g["away_team"]
            spread=next((o.get("point") for o in m.get("spreads",{}).get("outcomes",[]) if o["name"]==home),"")
            total=next((o.get("point") for o in m.get("totals",{}).get("outcomes",[]) if o["name"]=="Over"),"")
            ml={o["name"]:o.get("price","") for o in m.get("h2h",{}).get("outcomes",[])}
            ko=datetime.fromisoformat(g["commence_time"].replace("Z","+00:00")).astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")
            w.writerow({"kickoff_et":ko,"away_team":TEAM.get(away,away),"home_team":TEAM.get(home,home),"home_spread":spread,"total":total,"away_ml":ml.get(away,""),"home_ml":ml.get(home,""),"neutral":0,"source":f"DraftKings via The Odds API {now:%Y-%m-%d %H:%M ET}"})
    known=roster(); prop_rows=[]; td_rows=[]; skipped=set()
    for g in games:
        detail,remaining=get(f"sports/{SPORT}/events/{g['id']}/odds",{"bookmakers":"draftkings","markets":"player_pass_yds,player_rush_yds,player_reception_yds,player_anytime_td","oddsFormat":"american","dateFormat":"iso"})
        for key,market in dk_markets(detail).items():
            if key in PROP_MAP:
                seen=set()
                for o in market.get("outcomes",[]):
                    player=o.get("description","").strip(); point=o.get("point")
                    if not player or point is None or player in seen: continue
                    seen.add(player); team=known.get(player,"")
                    if not team: skipped.add(player); continue
                    prop_rows.append({"player":player,"team":team,"market":PROP_MAP[key],"line":point,"status":"","source":f"DraftKings via The Odds API {now:%Y-%m-%d %H:%M ET}"})
            elif key=="player_anytime_td":
                for o in market.get("outcomes",[]):
                    player=o.get("description",o.get("name","")).strip()
                    td_rows.append({"player":player,"team":known.get(player,""),"odds":o.get("price","") ,"source":f"DraftKings via The Odds API {now:%Y-%m-%d %H:%M ET}"})
    with props.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["player","team","market","line","status","source"]); w.writeheader(); w.writerows(prop_rows)
    with tds.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["player","team","odds","source"]); w.writeheader(); w.writerows(td_rows)
    print(f"Refreshed {len(games)} games, {len(prop_rows)} yard props, and {len(td_rows)} anytime-TD prices. Credits remaining: {remaining}")
    if skipped: print(f"Skipped {len(skipped)} players not yet in Dion's roster map.")
    cmd=[sys.executable,str(ROOT/"agent_dion_nfl.py"),"paper","--season","2026","--week","2","--game-lines",str(lines),"--props",str(props)]
    return subprocess.call(cmd,cwd=ROOT)

if __name__=="__main__": raise SystemExit(main())
