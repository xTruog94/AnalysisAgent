def parse_text_to_json(text):
    lines = text.split('\n')
    data = {}
    
    # Extract title
    data['title'] = lines[0].strip()
    
    # Parse main content
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Handle contract address
        if 'CA:' in line:
            data['contract_address'] = line.split('CA:')[1].split()[0].strip()
        
        # Handle LP
        elif 'LP:' in line:
            data['lp_address'] = line.split('LP:')[1].strip()
            
        # Handle exchange
        elif 'Exchange:' in line:
            data['exchange'] = line.split('Exchange:')[1].strip()
            
        # Handle market cap
        elif 'Market Cap:' in line:
            data['market_cap'] = line.split('Market Cap:')[1].strip()
            
        # Handle liquidity
        elif 'Liquidity:' in line:
            data['liquidity'] = line.split('Liquidity:')[1].strip()
            
        # Handle token price
        elif 'Token Price:' in line:
            data['token_price'] = line.split('Token Price:')[1].strip()
            
        # Handle pooled SOL
        elif 'Pooled SOL:' in line:
            data['pooled_sol'] = line.split('Pooled SOL:')[1].strip()
            
        # Handle total supply
        elif 'Total Supply:' in line:
            data['total_supply'] = line.split('Total Supply:')[1].strip()
            
        # Handle liquid supply
        elif 'Liquid Supply:' in line:
            data['liquid_supply'] = line.split('Liquid Supply:')[1].strip()
            
        # Handle holders
        elif 'Holders:' in line:
            data['holders'] = line.split('Holders:')[1].strip()
            
        # Handle top holders
        elif 'Top holders:' in line:
            data['top_holders'] = [x.strip() for x in line.split('Top holders:')[1].split('|')]
            
        # Handle security checks
        elif 'Renounced:' in line:
            data['renounced'] = '✅' in line
            
        elif 'Freeze Revoked:' in line:
            data['freeze_revoked'] = '✅' in line
            
        # Handle creator info
        elif 'Creator info:' in line:
            data['creator_info'] = {}
        elif 'Balance SOL:' in line:
            data['creator_info']['balance_sol'] = line.split('Balance SOL:')[1].strip()
        elif 'Balance USD:' in line:
            data['creator_info']['balance_usd'] = line.split('Balance USD:')[1].strip()
        elif 'Transactions:' in line:
            data['creator_info']['transactions'] = line.split('Transactions:')[1].strip()
        elif 'Dev Wallet Empty' in line:
            data['creator_info']['dev_wallet_empty'] = True
        elif 'Low Number Of Transactions' in line:
            data['creator_info']['low_transactions'] = True
            
    return data
