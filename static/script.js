document.addEventListener('DOMContentLoaded', () => {
    console.log("Event Planner frontend loaded.");

    // Example: Optional client-side form validation/enhancement
    const form = document.getElementById('add-event-form');

    if (form) {
        form.addEventListener('submit', (event) => {
            // Check if Title, Date, and Location are filled out
            const title = form.elements['title'].value.trim();
            const date = form.elements['date'].value.trim();
            const location = form.elements['location'].value.trim();

            if (!title || !date || !location) {
                alert("Please fill in the Event Title, Date, and Location.");
                // Note: The 'required' attribute in HTML handles this automatically,
                // but this demonstrates how JS validation would look.
                // event.preventDefault(); // Uncomment to stop form submission if validation fails
            }
        });
    }

    // Example: Confirmation dialog for deletion
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', (event) => {
            if (!confirm("Are you sure you want to delete this event?")) {
                event.preventDefault(); // Stop the form submission
            }
        });
    });
});