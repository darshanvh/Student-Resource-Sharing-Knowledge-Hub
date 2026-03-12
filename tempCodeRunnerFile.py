@app.route('/resource_snapshot', methods=['GET', 'POST'])
def resource_snapshot():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form.get('content')

        # Word count validation
        word_count = len(content.split())

        if word_count > 10000:
            flash('Content exceeds 10,000 word limit!', 'error')
            return redirect(url_for('resource_snapshot'))

        flash(f'Resource snapshot saved successfully! Word count: {word_count}', 'success')
        return redirect(url_for('resource_snapshot'))

    return render_template('resource_snapshot.html')


@app.route('/generate_summary', methods=['POST'])
def generate_summary():
    if 'user' not in session:
        return redirect(url_for('login'))

    content = request.form.get('content', '').strip()

    if not content:
        flash("Please enter content", "error")
        return redirect(url_for('resource_snapshot'))

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        Provide a very short and clear summary under 100 words.
        Focus only on key ideas.
        
        Content:
        {content}
        """

        response = model.generate_content(prompt)
        
        # Correctly access the response text
        summary = response.text.strip()

        return render_template("summary_result.html", summary=summary)

    except Exception as e:
        import traceback
        print("Error generating summary:")
        traceback.print_exc()
        
        # Fallback: Generate a simple summary without API
        words = content.split()
        if len(words) > 50:
            simple_summary = ' '.join(words[:50]) + '...\n\n[Note: AI summary unavailable. Please set valid GEMINI_API_KEY environment variable. Showing first 50 words as preview.]'
        else:
            simple_summary = content + '\n\n[Note: AI summary unavailable. Please set valid GEMINI_API_KEY environment variable.]'
        
        return render_template("summary_result.html", summary=simple_summary)