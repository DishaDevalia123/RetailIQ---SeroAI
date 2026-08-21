CREATE DATABASE RetailDB;
USE RetailDB;

CREATE TABLE Bill_Date_Sale (
    Customer_Name VARCHAR(255),
    Customer_Contact VARCHAR(50),
    BILL_DATE date,
    Bill_No VARCHAR(50),
    Item_Division VARCHAR (255), 
    Brand VARCHAR (255),
    Sub_Brand VARCHAR(255),
    Item_Description TEXT,
    Item_Barcode VARCHAR(100),
    Discount_Amount DECIMAL(10, 2),
    Total_Amount DECIMAL(10, 2),
    Item_Name VARCHAR(255),
    Sleeve VARCHAR(100),
    Size VARCHAR(50),
    SALE_QUANTITY INT,
    Store_Name VARCHAR(255),
    Color VARCHAR(100),
    Pattern VARCHAR(100),
    MRP DECIMAL (10, 2),
    DP DECIMAL (10, 2)
);


LOAD DATA INFILE "O:\\DISHA\\DISHA\\Gen AI\\Sero AI\\Final - Scripts\\30-10\\retail_sales_data_updated.csv"
INTO TABLE Bill_Date_Sale
FIELDS TERMINATED BY ',' 
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(
    Customer_Name,
    Customer_Contact,
    @raw_BILL_DATE, -- Temporarily store the raw date value
    Bill_No,
    Item_Division,
    Brand,
    Sub_Brand,
    Item_Description,
    Item_Barcode,
    Discount_Amount,
    Total_Amount,
    Item_Name,
    Sleeve,
    Size,
    SALE_QUANTITY,
    Store_Name,
    Color,
    Pattern,
    MRP,
    DP
)
SET BILL_DATE = STR_TO_DATE(@raw_BILL_DATE, '%d/%m/%Y');


SELECT BILL_DATE FROM Bill_Date_Sale WHERE BILL_DATE IS NOT NULL;

select * from Bill_Date_Sale;

TRUNCATE TABLE Bill_Date_Sale;

SELECT SUM(SALE_QUANTITY) FROM Bill_Date_Sale;

drop table Bill_Date_Sale;

SELECT 
    `Item_Name` ,
    SUM(`SALE_QUANTITY`) AS total_quantity_sold
FROM Bill_Date_Sale
WHERE `Sub_Brand` = '3'
  AND `MRP` BETWEEN 500 AND 1500
GROUP BY `Item_Name`, `MRP`
ORDER BY total_quantity_sold DESC;

SELECT 
    `Item_Name`,
    `Pattern`, `MRP`  
FROM Bill_Date_Sale
WHERE `Item_Name` = 'Tr278XA'; 

SELECT
  DATE_FORMAT(BILL_DATE, '%Y-%m') AS Month,
  SUM(SALE_QUANTITY) AS Total_Sale_Qty
FROM
  Bill_Date_Sale
WHERE
  Store_Name = 'Store 3'
  AND YEAR(BILL_DATE) = 2024
GROUP BY
  Month
ORDER BY
  Month;
  
SELECT 
    COUNT(*) AS returning_user_count,
    (COUNT(*) * 100.0) / 
    (SELECT COUNT(DISTINCT Customer_Contact) FROM Bill_Date_Sale) AS returning_user_percentage
FROM (
    SELECT Customer_Contact
    FROM Bill_Date_Sale
    GROUP BY Customer_Contact
    HAVING COUNT(DISTINCT Bill_No) > 1
) AS repeating_customers;

SELECT
  ROUND((COUNT(DISTINCT CASE WHEN Customer_Contact IN (SELECT Customer_Contact FROM Bill_Date_Sale WHERE STORE_NAME = 'store 2' GROUP BY Customer_Contact HAVING COUNT(DISTINCT BILL_DATE) > 1) THEN Customer_Contact END) /
          COUNT(DISTINCT Customer_Contact)) * 100, 2) AS Percentage_Returning_Customers
FROM
  Bill_Date_Sale
WHERE
  STORE_NAME = 'store 2';


SELECT 
    AVG(monthly_revenue) AS average_monthly_revenue
FROM (
    SELECT 
        YEAR(`BILL_DATE`) AS year,
        MONTH(`BILL_DATE`) AS month,
        SUM(`Total_Amount`) AS monthly_revenue
    FROM Bill_Date_Sale
    WHERE `Store_Name` = '3'
    GROUP BY YEAR(`BILL_DATE`), MONTH(`BILL_DATE`)
) AS monthly_data;

SELECT
    COUNT(DISTINCT B.Customer_Contact) AS Returning_Customers,
    (COUNT(DISTINCT B.Customer_Contact) * 100.0) /
        (SELECT COUNT(DISTINCT Customer_Contact)
         FROM Bill_Date_Sale
         WHERE Store_Name = 'Store 3'
           AND BILL_DATE >= '2024-10-01' AND BILL_DATE < '2025-01-01') AS Percentage_Returning_Customers
FROM Bill_Date_Sale B
WHERE B.Store_Name = 'Store 3'
  AND B.BILL_DATE >= '2024-10-01' AND B.BILL_DATE < '2025-01-01'
  AND B.Customer_Contact IN (
      SELECT Customer_Contact
      FROM Bill_Date_Sale
      GROUP BY Customer_Contact
      HAVING COUNT(DISTINCT Bill_No) > 1
  );

SELECT 
  COUNT(DISTINCT Customer_Name) /
  (SELECT COUNT(DISTINCT Customer_Name)
   FROM Bill_Date_Sale
   WHERE Store_Name = 'Store 3' AND
         BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31') * 100 as Percent
FROM Bill_Date_Sale
WHERE Store_Name = 'Store 3' AND
      BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31' AND
      Customer_Name IN
      (SELECT Customer_Name
       FROM Bill_Date_Sale
       WHERE Store_Name = 'Store 3' AND
             BILL_DATE < '2024-10-01');
             

WITH DailySales AS (
    SELECT
        BILL_DATE,
        SUM(SALE_QUANTITY) AS Total_Sale_Quantity,
        CASE 
            WHEN BILL_DATE BETWEEN '2024-10-15' AND '2024-11-05' THEN 'Diwali_Period'
            ELSE 'Before/After_Diwali'
        END AS Period
    FROM Bill_Date_Sale
    WHERE store_Name = 'store 3'
    GROUP BY BILL_DATE
),
RankedSales AS (
    SELECT
        *,
        LAG(Total_Sale_Quantity) OVER (ORDER BY BILL_DATE) AS Prev_Day_Sales,
        Total_Sale_Quantity - LAG(Total_Sale_Quantity) OVER (ORDER BY BILL_DATE) AS Sale_Diff
    FROM DailySales
)
SELECT *
FROM RankedSales
ORDER BY BILL_DATE;

SELECT
    SUM(SALE_QUANTITY) AS TOTAL_SALE_QUANTITY
FROM
    Bill_Date_Sale
WHERE
 Sub_Brand = '10'
    AND BILL_DATE >= DATE_SUB('2024-10-31', INTERVAL 30 DAY)
    AND BILL_DATE <= '2024-10-31'
    AND Store_Name = 'store 3';
    
SELECT
    YEAR(`BILL_DATE`) AS year,
    SUM(`Total_Amount`) AS revenue
FROM Bill_Date_Sale
WHERE MONTH(`BILL_DATE`) IN (3, 4, 5)
  AND YEAR(`BILL_DATE`) IN (2024)
  and `Sub_Brand` = '10'
GROUP BY year;


 WITH FestivalSales AS (
    SELECT
        CASE
            WHEN BILL_DATE BETWEEN '2023-10-01' AND '2023-10-31' THEN 'Diwali'
            WHEN BILL_DATE BETWEEN '2023-12-10' AND '2023-12-25' THEN 'Christmas'
            WHEN BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31' THEN 'Diwali'
            WHEN BILL_DATE BETWEEN '2024-12-10' AND '2024-12-25' THEN 'Christmas'
        END AS Festival,
        SUM(SALE_QUANTITY) AS Total_Sale_Quantity,
        SUM(Total_Amount) AS Total_Sale_Amount
    FROM Bill_Date_Sale
    WHERE Store_Name IN ('PRFT')
    GROUP BY Festival
)
SELECT * FROM FestivalSales;

 SELECT
    SUM(`SALE_QUANTITY`) AS Total_qty,
    SUM(`Total_Amount`) AS Total_amount
FROM Bill_Date_Sale
WHERE `Store_Name` = 'PRFTL';

 SELECT
    AVG(monthly_sales_qty) AS average_monthly_sales_qty
FROM (
    SELECT
        YEAR(`BILL_DATE`) AS year,
        MONTH(`BILL_DATE`) AS month,
        SUM(`SALE_QUANTITY`) AS monthly_sales_qty
    FROM Bill_Date_Sale
    WHERE 1=1
    AND `Store_Name` = 'PRFT'
    AND (`BILL_DATE` BETWEEN '2023-10-01' AND '2023-10-31' OR `BILL_DATE` BETWEEN '2024-10-01' AND '2024-10-31')
    GROUP BY YEAR(`BILL_DATE`), MONTH(`BILL_DATE`)
) AS monthly_data;

SELECT
    `Store_Name`,
    SUM(`SALE_QUANTITY`) AS sale_qty,
    SUM(`Total_Amount`) AS total_amt
FROM Bill_Date_Sale
WHERE `Store_Name` IN (SELECT DISTINCT `Store_Name` FROM Bill_Date_Sale)
AND `Store_Name` != 'PRFT'
UNION ALL
SELECT
    'PRFT',
    SUM(`SALE_QUANTITY`),
    SUM(`Total_Amount`)
FROM Bill_Date_Sale
WHERE `Store_Name` = 'PRFT'
ORDER BY sale_qty DESC;

SELECT
    `Store_Name`,
    SUM(`SALE_QUANTITY`) AS Total_Sale_Qty,
    SUM(`Total_Amount`) AS Total_Sale_Amount
FROM Bill_Date_Sale
WHERE `Store_Name` IN ('PRFTL', 'PRFCO', 'PRFT', 'MEM')
GROUP BY `Store_Name`
ORDER BY Total_Sale_Amount DESC;

SELECT
    `Brand`, SUM(`SALE_QUANTITY`) AS sale, SUM(`Total_Amount`) AS total_sales
FROM Bill_Date_Sale
WHERE 1=1 AND `Store_Name` = 'PRFTL' AND `BILL_DATE` BETWEEN '2024-11-01' AND '2024-11-30'
GROUP BY `Brand`
ORDER BY total_sales DESC
LIMIT 1;

SELECT
    AVG(monthly_sale_qty) AS average_monthly_sale_qty
FROM (
    SELECT
        YEAR(`BILL_DATE`) AS year,
        MONTH(`BILL_DATE`) AS month,
        SUM(`SALE_QUANTITY`) AS monthly_sale_qty
    FROM Bill_Date_Sale
    WHERE 1=1 AND `Store_Name` = 'PRFT'
    GROUP BY YEAR(`BILL_DATE`), MONTH(`BILL_DATE`)
) AS monthly_data;

SELECT
    YEAR(BILL_DATE) AS year,
    MONTH(BILL_DATE) AS month,
    AVG(SALE_QUANTITY) AS avg_monthly_sale_qty
FROM Bill_Date_Sale
WHERE Store_Name = 'PRFCO'
  AND BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
GROUP BY year(BILL_DATE), month(BILL_DATE)
ORDER BY year(BILL_DATE), month(BILL_DATE);

SELECT
    MONTH(BILL_DATE) AS month,
    SUM(SALE_QUANTITY) AS sale_qty,
    SUM(Total_Amount) AS total_amount
FROM Bill_Date_Sale
WHERE Store_Name = 'PRFCO'
AND BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
GROUP BY MONTH(BILL_DATE)
ORDER BY month;

SELECT
  Store_Name,
  AVG(`Discount Amount`) AS avg_discount_amount
FROM
  Bill_Date_Sale
WHERE
  BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
GROUP BY
  Store_Name
ORDER BY
  avg_discount_amount DESC;
  
SELECT AVG(`Total_Amount`) AS Avg_Sale_Amount
FROM Bill_Date_Sale
WHERE 1=1
AND `Brand` = 'Park Avenue'
AND `BILL_DATE` NOT BETWEEN '2024-10-01' AND '2024-10-31'
AND `BILL_DATE` NOT BETWEEN '2024-01-01' AND '2024-01-15'
AND `BILL_DATE` NOT BETWEEN '2024-12-10' AND '2024-12-25'
AND `BILL_DATE` NOT BETWEEN '2024-03-01' AND '2024-05-31'
AND Customer_Name IN (
  SELECT Customer_Name
  FROM
    Bill_Date_Sale
  GROUP BY Customer_Name
  HAVING COUNT(DISTINCT BILL_No) > 1
);

SELECT AVG(`Total_Amount`) AS Avg_Sale_Value
FROM Bill_Date_Sale
WHERE 1=1
AND `Brand` = 'Park Avenue'
AND `BILL_DATE` NOT BETWEEN '2024-10-01' AND '2024-10-31'
AND `BILL_DATE` NOT BETWEEN '2024-01-01' AND '2024-01-15'
AND `BILL_DATE` NOT BETWEEN '2024-12-10' AND '2024-12-25'
AND `BILL_DATE` NOT IN ('2024-03-01', '2024-04-01', '2024-05-01');

SELECT
    `Store_Name`,
    AVG(`Total_Amount` / `SALE_QUANTITY`) AS Average_Sale_Value
FROM Bill_Date_Sale
WHERE 1=1
AND `Brand` = 'Park Avenue'
GROUP BY `Store_Name`;

SELECT 
    `Store_Name`, `Sub_Brand`,
    SUM(`Total_Amount`) AS total_sales_amount
FROM Bill_Date_Sale
WHERE `Sub_Brand` IN ('Urban', 'Sport')
GROUP BY `Store_Name`, `Sub_Brand`
ORDER BY total_sales_amount DESC;

SELECT
    CASE
        WHEN BILL_DATE BETWEEN '2024-01-01' AND '2024-01-15' THEN 'Pongal'
        WHEN BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31' THEN 'Diwali'
        WHEN BILL_DATE = '2024-12-25' THEN 'Christmas'
        WHEN BILL_DATE BETWEEN '2024-03-01' AND '2024-05-31' THEN 'Summer'
    END AS Festival,
    Sub_Brand,
    SUM(SALE_QUANTITY) AS Total_qty,
    SUM(Total_Amount) AS Total_amount
FROM Bill_Date_Sale
WHERE Sub_Brand IN ('Travel', 'Urban')
GROUP BY Festival, Sub_Brand;

WITH Repeat_Customers AS (
  SELECT Customer_Name
  FROM Bill_Date_Sale
  GROUP BY Customer_Name
  HAVING COUNT(DISTINCT BILL_No) > 1
),
Labeled_Orders AS (
  SELECT 
    Customer_Name,
    Total_Amount,
    CASE 
      WHEN BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31' THEN 'Festive'
      WHEN BILL_DATE BETWEEN '2024-12-10' AND '2024-12-25' THEN 'Festive'
      WHEN BILL_DATE BETWEEN '2024-01-01' AND '2024-01-15' THEN 'Festive'
      WHEN BILL_DATE BETWEEN '2024-03-01' AND '2024-05-31' THEN 'Festive'
      ELSE 'Non-Festive'
    END AS Season
  FROM Bill_Date_Sale
  WHERE Customer_Name IN (SELECT Customer_Name FROM Repeat_Customers)
)
SELECT 
  Season,
  AVG(Total_Amount) AS avg_order_value
FROM Labeled_Orders
GROUP BY Season;

SELECT
    DATE_FORMAT(BILL_DATE, '%b') AS Month,
    SUM(CASE WHEN Brand = '{brand_1}' THEN SALE_QUANTITY      END) AS brand_1_Qty,
    SUM(CASE WHEN Brand = '{brand_1}'  THEN Total_Amount  END) AS brand_1_Amt,
    SUM(CASE WHEN Brand = '{brand_2}'  THEN SALE_QUANTITY      END) AS brand_2_Qty,
    SUM(CASE WHEN Brand = '{brand_2}'  THEN Total_Amount  END) AS brand_2_Amt
FROM Bill_Date_Sale
WHERE Brand IN ('{brand_1}', '{brand_2}')
GROUP BY DATE_FORMAT(BILL_DATE, '%b'), MONTH(BILL_DATE)
ORDER BY MONTH(BILL_DATE);

SELECT 
    MONTH(BILL_DATE) AS month,
    SUM(CASE WHEN Brand = 'Blackberrys' THEN SALE_QUANTITY END) AS Blackberrys_Qty,
    SUM(CASE WHEN Brand = 'Blackberrys' THEN Total_Amount END) AS Blackberrys_Amt,
    SUM(CASE WHEN Brand = 'Park Avenue' THEN SALE_QUANTITY END) AS Park_Avenue_Qty,
    SUM(CASE WHEN Brand = 'Park Avenue' THEN Total_Amount END) AS Park_Avenue_Amt
FROM Bill_Date_Sale
WHERE Brand IN ('Blackberrys', 'Park Avenue')
GROUP BY month
ORDER BY MONTH(BILL_DATE);

SELECT
    `Store_Name`,
    YEAR(`BILL_DATE`) AS year,
    MONTH(`BILL_DATE`) AS month,
    SUM(`SALE_QUANTITY`) AS sale_quantity_quantity,
    SUM(`Total_Amount`) AS total_amount
FROM
    Bill_Date_Sale
WHERE
    `BILL_DATE` BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY
    `Store_Name`, year, month
ORDER BY
    year, month;
    
SELECT
  CASE
    WHEN BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31' THEN 'Diwali 2024'
    WHEN BILL_DATE BETWEEN '2024-01-01' AND '2024-01-15' THEN 'Pongal 2024'
    WHEN BILL_DATE BETWEEN '2024-12-10' AND '2024-12-25' THEN 'Christmas 2024'
  END AS festival,
  SUM(SALE_QUANTITY) AS sale_quantity,
  SUM(Total_Amount) AS total_amount
FROM Bill_Date_Sale
WHERE Store_Name = 'PRFT'
GROUP BY festival
ORDER BY festival;