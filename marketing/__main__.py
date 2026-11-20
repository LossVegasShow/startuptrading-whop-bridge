"""python -m marketing [--out DIR] [--metrics DIR] [--briefs N]

Needs ANTHROPIC_API_KEY in the environment.
"""
import argparse
import os
import sys

from . import pipeline


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m marketing', description='Run the weekly marketing team.')
    ap.add_argument('--out', default='marketing/out', help='Where to write the review queue.')
    ap.add_argument('--metrics', default='marketing/metrics', help='Folder of CSV exports (optional).')
    ap.add_argument('--briefs', type=int, default=5, help='How many content pieces to produce.')
    args = ap.parse_args(argv)

    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('ANTHROPIC_API_KEY is not set. Add it as a repository secret (see marketing/README.md).',
              file=sys.stderr)
        return 2

    import anthropic  # imported here so the tests don't need the SDK installed
    client = anthropic.Anthropic(max_retries=4)
    try:
        out, result = pipeline.run(client, args.out, args.metrics, max_briefs=args.briefs)
    except anthropic.AuthenticationError:
        print('The Anthropic API key was rejected. Check the ANTHROPIC_API_KEY secret.', file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print('Rate limited by the Anthropic API after retries. Run again later.', file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f'Anthropic API error {e.status_code}: {e.message}', file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print('Could not reach the Anthropic API.', file=sys.stderr)
        return 1
    except pipeline.agents.AgentError as e:
        print(f'A planning step failed: {e}', file=sys.stderr)
        return 1
    ready = sum(i['status'] == pipeline.READY for i in result['items'])
    print(f"Wrote {out}/queue.md: {ready} of {len(result['items'])} pieces ready for review.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
