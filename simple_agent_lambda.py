"""
Simple Lambda for listing and invoking AgentCore agents.
No authentication - uses Lambda's IAM role.
"""
import json
import boto3


def lambda_handler(event, context):
    """Handle agent listing and invocation."""

    # Get tool name from Gateway context
    tool_name = ""
    if context.client_context and context.client_context.custom:
        tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', '')

    # Fallback: check event body for tool_name (for testing)
    if not tool_name and isinstance(event, dict):
        tool_name = event.get('tool_name', '')

    region = 'eu-central-1'

    try:
        # LIST AGENTS
        if 'list_agents' in tool_name:
            client = boto3.client('bedrock-agentcore-control', region_name=region)
            agents = []
            next_token = None

            while True:
                params = {'maxResults': 100}
                if next_token:
                    params['nextToken'] = next_token

                response = client.list_agent_runtimes(**params)

                for agent in response.get('agentRuntimes', []):
                    agents.append({
                        'name': agent.get('agentRuntimeName', ''),
                        'arn': agent.get('agentRuntimeArn', ''),
                        'status': agent.get('status', ''),
                    })

                next_token = response.get('nextToken')
                if not next_token:
                    break

            return {
                'statusCode': 200,
                'body': json.dumps({'agents': agents, 'count': len(agents)})
            }

        # INVOKE AGENT
        elif 'invoke_agent' in tool_name:
            client = boto3.client('bedrock-agentcore', region_name=region)

            # Get parameters from event
            agent_arn = event.get('agent_arn')
            prompt = event.get('prompt')
            session_id = event.get('session_id', '')

            if not agent_arn:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'agent_arn is required'})
                }

            if not prompt:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'prompt is required'})
                }

            # Build payload
            payload = json.dumps({
                'prompt': prompt,
                'session_id': session_id
            })

            # Invoke agent
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=session_id or 'default',
                payload=payload.encode(),
                qualifier='DEFAULT'
            )

            # Collect streaming response
            completion = ''
            streaming_body = response.get('response')

            if streaming_body:
                for chunk in streaming_body.iter_lines():
                    if not chunk:
                        continue
                    chunk_str = chunk.decode('utf-8')
                    if not chunk_str or chunk_str.startswith(':'):
                        continue
                    if chunk_str.startswith('data:'):
                        chunk_str = chunk_str.split(':', 1)[1].strip()
                    if chunk_str:
                        try:
                            data = json.loads(chunk_str)
                            if data.get('type') == 'text':
                                completion += data.get('text', '')
                        except json.JSONDecodeError:
                            pass

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'completion': completion,
                    'session_id': response.get('runtimeSessionId', session_id)
                })
            }

        # UNKNOWN TOOL
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Unknown tool: {tool_name}'})
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
