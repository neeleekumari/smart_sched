
@app.route('/api/auth/user', methods=['DELETE'])
def delete_current_user():
    """Delete the currently authenticated user account"""
    try:
        # Verify Token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1].strip()
        auth_manager = get_auth_manager()
        valid, user = auth_manager.verify_token(token)
        
        if not valid or not user:
            try: auth_manager.db.close()
            except: pass
            return jsonify({'error': 'Invalid or expired token'}), 401
            
        try:
            # Perform Deletion
            # Note: User model cascades deletes to related Teacher/Subject/etc profiles
            auth_manager.db.delete(user)
            auth_manager.db.commit()
            return jsonify({'message': 'Account deleted successfully'}), 200
        finally:
            try: auth_manager.db.close()
            except: pass
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
