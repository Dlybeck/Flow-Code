module Main where

emphasize value = value * value

calculate value = emphasize value + 1

main = print (calculate 2)
