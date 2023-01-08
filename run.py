#!/usr/bin/env python3

import pandas as pd
import requests
import itertools
import os
from datetime import datetime

LINEAR_PATH = "https://raw.githubusercontent.com/mastodon/joinmastodon/master/data/linear.json"
LINEAR_LOCAL = "linear.csv"
MESSAGE_PATH = "readme.md"

def tidy_up(issues: dict, columns: list) -> pd.core.frame.DataFrame:
    """
    Flatten the original data
    """
    df = pd.concat(
        [
            pd.DataFrame(
                [{**{"type": issuetype["type"]}, **i} for i in issuetype["items"]]
            )
            for issuetype in issues
        ]
    )
    df.set_index("id", inplace=True)
    return df.sort_index()[columns]

def get_records(df: pd.core.frame.DataFrame, items: list) -> list:

    dfi = df.loc[items].copy()
    return dfi.reset_index().to_dict(orient="records")

def issue_appeared(old: pd.core.frame.DataFrame, new: pd.core.frame.DataFrame) -> list:
    """
    What new issues appeared
    """
    
    appeared = [i for i in new.index if i not in old.index]
    return get_records(new, appeared)

def issue_dropped(old: pd.core.frame.DataFrame, new: pd.core.frame.DataFrame) -> list:
    """
    What new issues disappeared
    """

    dropped = [i for i in old.index if i not in new.index]
    return get_records(old, dropped)

def issue_changed(old: pd.core.frame.DataFrame, new: pd.core.frame.DataFrame) -> list:
    """
    What issues changed
    """
    
    common = [i for i in old.index if i in new.index]
    changes = old.loc[common].compare(new.loc[common])
    new_dict = new.to_dict(orient='index')
    formatted = [
        [
            {
                **{'id': i, 'title':new_dict[i]['title'], 'attribute': attr}, **{a:b for a,b in zip(['old', 'new'], value[i].tolist())}
            } for attr, value in row.dropna().reset_index().groupby('level_0')
        ] for i, row in changes.iterrows()
    ]
    return list(itertools.chain.from_iterable(formatted))

def get_changes(old: pd.core.frame.DataFrame, new: pd.core.frame.DataFrame) -> dict:
    """
    How is the new data different
    """
    
    changes = {
        "appeared": issue_appeared(old, new), 
        "dropped": issue_dropped(old, new),
        'changed': issue_changed(old, new)
    }
    return changes

def write_entries(changes:dict) -> list:
    """
    Compose a message for each change
    """

    priorities = {
        0: 'no priority',
        1: 'urgent',
        2: 'high priority',
        3: 'medium priority',
        4: 'low priority'
    }
    types = {
        'started': 'in progress',
        'unstarted': 'planned',
        'backlog': 'exploring'
    }
    
    def write_issue(issue:dict) -> str:
        return f'*{issue["title"]}* (`{issue["id"]}`) `{types[issue["type"]]}` `{priorities[issue["priority"]]}`'
    
    def write_change(change:dict) -> str:
        
        if change['attribute'] == 'priority':
            o, n = [priorities[change[i]] for i in ['old', 'new']]
        elif change['attribute'] == 'types':
            o, n = [types[change[i]] for i in ['old', 'new']]
        else:
            o, n = [change[i] for i in ['old', 'new']]
            
        return f'- **change** in *{change["title"]}* (`{change["id"]}`): `{change["attribute"]}` from \"{o}\" to \"{n}\"'
    
    entries = []
    for e in changes['appeared']:
        entries.append(f'- **new**: {write_issue(e)}')
    for e in changes['dropped']:
        entries.append(f'- **dropped**: {write_issue(e)}')
    for c in changes['changed']:
        entries.append(write_change(c))
    return entries

def save_message(entries:list):
    """
    Save the message
    """
    
    today = datetime.utcnow().strftime('%B %d, %Y')
    
    if os.path.exists(MESSAGE_PATH):
        with open(MESSAGE_PATH, 'r') as f:
            message = [row.strip() for row in f.readlines()]
    else:
        message = []
    
    message = ([f'## {today}'] + entries) + message
    
    with open(MESSAGE_PATH,'w+') as f:
        f.write('\n'.join(message))


if __name__ == "__main__":

    old = pd.read_csv(LINEAR_LOCAL, index_col="id")
    response = requests.get(LINEAR_PATH)
    new = tidy_up(response.json(), ['type', 'title', 'priority'])
    changes = get_changes(old, new)
    entries = write_entries(changes)
    if entries:
        save_message(entries)
        new.to_csv(LINEAR_LOCAL)
