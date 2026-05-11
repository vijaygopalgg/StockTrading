import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# -----------------------------
# 1. Generate the dataset
# -----------------------------
n = 1000

# x1 and x2 in the range [1, 20]
x1 = np.random.randint(1, 21, n)
x2 = np.random.randint(1, 21, n)

# target function: y = x1^2 + x2
y = x1**2 + x2

# create dataframe
df = pd.DataFrame({
    "x1": x1,
    "x2": x2,
    "y": y
})

# -----------------------------
# 2. Prepare data for training
# -----------------------------
X = df[["x1", "x2"]]   # features
Y = df["y"]            # target

# -----------------------------
# 3. Train Linear Regression
# -----------------------------
model = LinearRegression()
model.fit(X, Y)

# -----------------------------
# 4. Print model parameters
# -----------------------------
print("Model Linear Regression Coefficients:")
print(f"  Coefficient for x1: {model.coef_[0]}")
print(f"  Coefficient for x2: {model.coef_[1]}")
print(f"Intercept (constant): {model.intercept_}")

# -----------------------------
# 2. Polynomial feature expansion
# -----------------------------
poly = PolynomialFeatures(degree=2, include_bias=False)
X_poly = poly.fit_transform(X)

# -----------------------------
# 3. Train polynomial regression
# -----------------------------
model = LinearRegression()
model.fit(X_poly, y)

# -----------------------------
# 4. Print learned parameters
# -----------------------------
print("Feature names:", poly.get_feature_names_out(["x1", "x2"]))
print("Coefficients:", model.coef_)
print("Intercept:", model.intercept_)