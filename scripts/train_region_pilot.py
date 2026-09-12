"""Train one reviewable regional pilot; never replaces Massachusetts models."""
import argparse
import json
from pathlib import Path

from wildlocate.core.training import TrainingSession, new_job_id
from wildlocate.core.regions import region_root

parser=argparse.ArgumentParser()
parser.add_argument('--region',required=True,choices=['FL','AZ'])
parser.add_argument('--species',required=True)
parser.add_argument('--observations',type=int,default=400)
args=parser.parse_args()
session=TrainingSession(new_job_id(),lambda message: print(message,flush=True),
                        region=args.region,max_observations=args.observations)
session.resolve(args.species)
session.prepare()
result=session.train()
path=region_root(args.region)/'pilot-result.json'
path.write_text(json.dumps(result,indent=2))
print('PILOT COMPLETE',json.dumps(result),flush=True)
