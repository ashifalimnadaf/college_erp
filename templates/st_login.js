// Dummy user data (for demo)
const users = [
  { username: "student1", password: "12345", role: "student" },
  { username: "teacher1", password: "abcde", role: "teacher" }

];

// Handle form submission
document.getElementById("loginForm").addEventListener("submit", function(e) {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const errorMsg = document.getElementById("error-message");

  // Find user
  const user = users.find(u => u.username === username && u.password === password);

  if (user) {
    // Save to localStorage (simulate login session)
    localStorage.setItem("loggedInUser", JSON.stringify(user));
    if (user.role === "student") {
      window.location.href = "student_dashboard.html";
}   else if (user.role === "teacher") {
      window.location.href = "teacher_dashboard.html";
}

  } 
  else {
    errorMsg.textContent = "Invalid username or password!";
  }
});
